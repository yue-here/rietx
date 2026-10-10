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

import re
from fractions import Fraction

import numpy as np
import pytest

from rietx.crystallography.magnetic import isotropy
from rietx.crystallography.magnetic.operators import (
    MagneticGroup,
    MagneticOperator,
    allowed_displacement_basis,
    allowed_moment_basis,
    identify,
    in_span,
)
from rietx.crystallography.representation import irreps, modes
from tests.space_group_sample import TRAP_SAMPLE

GAMMA = (Fraction(0), Fraction(0), Fraction(0))
HALF = (Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))

#: The 230-setting sweeps run over the trap-chosen sample in the fast tier and
#: over every group in the nightly (``tests/space_group_sample.py``, WP-1547).
SWEEPS = [pytest.param(frozenset(TRAP_SAMPLE), id="sample"),
          pytest.param(frozenset(range(1, 231)), id="all-230", marks=pytest.mark.slow)]


def _standard_settings(numbers):
    """The first ITB setting of each group whose number is in ``numbers``."""
    import gemmi

    settings = {}
    for entry in gemmi.spacegroup_table_itb():
        if entry.number in numbers and entry.number not in settings:
            settings[entry.number] = entry.xhm()
    assert len(settings) == len(numbers)
    return list(settings.values())


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


@pytest.mark.parametrize("numbers", SWEEPS)
def test_the_sweep_over_the_230_settings_at_gamma(numbers):
    """Every standard setting, one special site, every candidate consistent.

    Measured 2026-09-06 on spglib 2.7.0 / gemmi 0.7.5: **1199 candidates over
    the 230 standard settings**, every one identified, every configuration
    inside its own group's allowed span, and **not one of type IV** — which is
    the derived statement that a zero propagation vector cannot produce an
    anti-translation.  The trap sample gives 140 of them (2026-10-09).  The
    whole sweep took 44-50 s on CI legs (WP-1506, WP-1547), so it runs
    nightly.
    """
    total, types = 0, {}
    for setting in _standard_settings(numbers):
        found = isotropy.candidates(setting, (0, 0, 0), GAMMA)   # verify=True inside
        total += len(found)
        for candidate in found:
            assert candidate.identification is not None, f"{setting} {candidate.label}"
            types[candidate.msg_type] = types.get(candidate.msg_type, 0) + 1
    if len(numbers) == 230:
        assert (total, types) == (1199, {1: 305, 3: 894})
    else:
        assert (total, types) == (140, {1: 36, 3: 104})


@pytest.mark.parametrize("numbers", SWEEPS)
def test_the_real_amplitude_count_closes_at_three_n(numbers):
    """Σ over the kept irreps of the free real amplitudes is 3N, at every setting.

    It closes only because a genuinely complex irrep and its conjugate are one
    physically irreducible representation and only one of the pair is kept; with
    both, P4 at Γ on a general site gives 3 + 6 + 6 + 3 = 18 against 3N = 12.
    """
    mismatches = []
    for setting in _standard_settings(numbers):
        for site in ((0, 0, 0), (0.11, 0.13, 0.17)):
            representation = modes.magnetic_representation(setting, site, GAMMA)
            kept, total = [], 0
            for irrep in irreps.small_irreps(setting, GAMMA):
                if isotropy._is_conjugate_of_a_kept_irrep(irrep, kept):
                    continue
                basis = modes.basis_vectors(representation, irrep)
                if basis.multiplicity == 0:
                    continue
                kept.append(irrep)
                total += basis.free_real_amplitudes
            if total != 3 * representation.n_atoms:
                mismatches.append((setting, site, total, 3 * representation.n_atoms))
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
    """[100], [010] and [001] are one candidate with three conjugate directions.

    Three orientations, not three candidates — and not three domains: each
    orientation also has its time-reversed (180°) domain, which shares its
    stabiliser and so is not counted here (issue #608).
    """
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


#: Issue #608's hand table, [G_k1′ : H] within one arm of the star, and the
#: count over every arm: (parent, site, k, BNS, per arm, all arms).  MnF₂, LaMnO₃
#: and Cr₂O₃ have the 180° pair only; MnO 15.90 has three orientations × 2 in
#: the arm of k and four arms (the L-point star of F m -3 m).
DOMAIN_CASES = [
    ("P 4_2/m n m", (0, 0, 0), GAMMA, "136.499", 2, 2),
    ("P n m a", (0, 0, 0), GAMMA, "62.448", 2, 2),
    ("R -3 c", (0, 0, 0.3476), GAMMA, "167.106", 2, 2),
    ("F m -3 m", (0, 0, 0), HALF, "15.90", 6, 24),
]


def _independent_domain_count(found, candidate):
    """[G_k1′ : H] with no rietx group code: 2·|Ḡ_k|·(lattice points per cell) / |H|.

    |Ḡ_k| counts gemmi's coset representatives R with Rᵀk ≡ k (reciprocal space
    carries the transposed rotation, root ``CLAUDE.md``), the lattice points are
    the parent's centrings times |det P|, and |H| is the number of operations
    spglib finds on the generated structure, a non-magnetic general orbit of the
    parent pinning the parent symmetry.
    """
    import gemmi
    spglib = pytest.importorskip("spglib")
    parent = gemmi.SpaceGroup(found.space_group.xhm())
    k = np.array([float(c) for c in found.k])
    centrings = [np.array(c, dtype=float) / 24 for c in parent.operations().cen_ops]
    fixes = 0
    for op in parent.operations().sym_ops:
        d = np.array(op.rot, dtype=float).T @ k / 24 - k
        fixes += bool(np.allclose(d, np.round(d))
                      and all(abs(d @ t - round(d @ t)) < 1e-9 for t in centrings))
    basis = np.array([[float(v) for v in row] for row in candidate.cell.basis])
    grey = 2 * fixes * round(abs(np.linalg.det(basis)) * len(centrings))
    general = {tuple(np.round(np.array(op.apply_to_xyz([0.1234, 0.2345, 0.3456])) % 1.0, 9))
               for op in parent.operations()}
    inverse = np.linalg.inv(basis)
    span = int(np.ceil(np.abs(basis).sum(axis=1).max())) + 1
    dummy = sorted({tuple(np.round(np.round(inverse @ (np.array(p) + np.array(n) - span), 9)
                                   % 1.0, 9) % 1.0)
                    for p in general for n in np.ndindex(*(2 * span + 1,) * 3)})
    moments = candidate.moments(np.random.default_rng(5).normal(
        size=candidate.free_amplitudes)) @ found.lattice
    cell = (found.lattice, np.vstack([np.asarray(candidate.positions) % 1.0, dummy]),
            [25] * len(candidate.positions) + [8] * len(dummy),
            np.vstack([moments, np.zeros((len(dummy), 3))]))
    data = spglib.get_magnetic_symmetry_dataset(cell, symprec=1e-4, mag_symprec=1e-3)
    assert data is not None, candidate.label
    assert grey % len(data.rotations) == 0
    return grey // len(data.rotations)


@pytest.mark.parametrize("case", DOMAIN_CASES, ids=[c[0] for c in DOMAIN_CASES])
def test_the_table_prints_the_domain_count_not_the_conjugate_directions(case):
    """Issue #608: the column called "domains" printed ``direction.conjugates``.

    That is the number of conjugate directions, which leaves out the 180°
    (time-reversed) domain, so it printed 1 / 1 / 1 / 3 here against the hand
    count 2 / 2 / 2 / 6.  :meth:`CandidateSet.domain_counts` is checked three
    ways: against the hand table, against a count that uses no rietx group code
    (spglib's |H| on the generated structure), and against the cosets
    :func:`isotropy._domain_operations` builds for the powder sums, on every
    candidate of the set.  The printed table carries both numbers.
    """
    group, site, k, bns, per_arm, all_arms = case
    found = isotropy.candidates(group, site, k)
    counts = found.domain_counts()
    little = irreps.little_group(found.space_group, found.k)
    for candidate, (arm, total) in zip(found, counts):
        assert arm == len(isotropy._domain_operations(candidate, little)), candidate.label
        assert total == arm * len(irreps.star(found.space_group, found.k))
    index = next(i for i, c in enumerate(found) if c.bns_number == bns)
    candidate = found[index]
    assert counts[index] == (per_arm, all_arms)
    assert _independent_domain_count(found, candidate) == per_arm
    assert candidate.direction.conjugates == per_arm // 2   # the number it printed
    cells = [re.split(r"\s{2,}", line.strip()) for line in str(found).splitlines()]
    header = next(c for c in cells if c[0] == "irrep")
    assert header[4:6] == ["domains/arm", "domains"]
    row = next(c for c in cells if c[:3] == [candidate.irrep_label, candidate.direction.label, bns])
    assert row[4:6] == [str(per_arm), str(all_arms)]


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


#: The four public cases of issue #607 (parent, magnetic site, k): MnO, MnF₂,
#: Cr₂O₃ and LaMnO₃, the parents and sites of :data:`PUBLISHED` and arm A.
VERIFY_CASES = [
    ("F m -3 m", (0, 0, 0), HALF),
    ("P 4_2/m n m", (0, 0, 0), GAMMA),
    ("R -3 c", (0, 0, 0.3476), GAMMA),
    ("P n m a", (0, 0, 0), GAMMA),
]


def _planted_group(stabiliser_sign):
    """``_candidate_group`` (magnetic branch) with the operator's time-reversal sign replaced.

    ``stabiliser_sign(eta, eps, det)`` returns the sign the operator carries; the
    honest rule is η·ε(Δ).  The test file's own copy of the loop, so a plant
    changes the operator list and nothing else — the configurations, the
    stabiliser and the permutation phases are untouched.
    """
    def build(little, cell, stabilizer, kind="magnetic"):
        inverse = isotropy._exact_inverse(cell.basis)
        forward = [[isotropy._frac(v) for v in row] for row in cell.basis]
        operations = {}
        for index, eta in stabilizer:
            integral = isotropy._rotation_in_cell(little.rotations[index], inverse, forward)
            det = round(float(np.linalg.det(np.array(little.rotations[index], dtype=float))))
            for shift, eps in cell.translations:
                t = [little.translations[index][i] + shift[i] for i in range(3)]
                in_cell = [sum(inverse[i][j] * t[j] for j in range(3)) for i in range(3)]
                operations.setdefault(MagneticOperator.build(
                    integral, in_cell, stabiliser_sign(eta, eps, det)), None)
        return MagneticGroup.from_operations(isotropy._close_operations(operations))
    return build


#: Issue #607's two plants: the anti-translation sign dropped (η·ε(Δ) → η), and
#: a polar vector's sign read for an axial one (η·ε(Δ) → η·ε(Δ)·det R).
PLANTS = {
    "no-anti-translation": _planted_group(lambda eta, eps, det: eta),
    "polar-for-axial": _planted_group(lambda eta, eps, det: eta * eps * det),
}


def _spglib_bns(found, candidate):
    """spglib's BNS number for the structure the candidate generates (the oracle).

    The magnetic atoms carry a random member of the family; one non-magnetic
    *general* orbit of the parent pins the parent symmetry, because a special
    site's own point set can have accidental extra symmetry (the hostile review
    of 2026-10-02 measured it).  Nothing here reads the isotropy machinery
    beyond the candidate's own positions and moments.
    """
    import gemmi
    spglib = pytest.importorskip("spglib")
    parent = gemmi.SpaceGroup(found.space_group.xhm())
    general = {tuple(np.round(np.array(op.apply_to_xyz([0.1234, 0.2345, 0.3456])) % 1.0, 9))
               for op in parent.operations()}
    basis = np.array([[float(v) for v in row] for row in candidate.cell.basis])
    inverse = np.linalg.inv(basis)
    span = int(np.ceil(np.abs(basis).sum(axis=1).max())) + 1
    dummy = set()
    for point in general:
        for shift in np.ndindex(*(2 * span + 1,) * 3):
            x = inverse @ (np.array(point) + np.array(shift) - span)
            dummy.add(tuple(np.round(np.round(x, 9) % 1.0, 9) % 1.0))
    dummy = np.array(sorted(dummy))
    rng = np.random.default_rng(3)
    moments = candidate.moments(rng.normal(size=candidate.free_amplitudes)) @ found.lattice
    cell = (found.lattice,
            np.vstack([np.asarray(candidate.positions) % 1.0, dummy]),
            [25] * len(candidate.positions) + [8] * len(dummy),
            np.vstack([moments, np.zeros((len(dummy), 3))]))
    data = spglib.get_magnetic_symmetry_dataset(cell, symprec=1e-4, mag_symprec=1e-3)
    assert data is not None, candidate.label
    return spglib.get_magnetic_spacegroup_type(data.uni_number).bns_number


@pytest.mark.parametrize("case", VERIFY_CASES, ids=[c[0] for c in VERIFY_CASES])
def test_the_honest_tree_verifies_and_spglib_agrees_with_every_label(case):
    """Positive arm of issue #607: every candidate verifies, and its label is spglib's.

    The plants below must turn ``verified`` False; this is the arm that says the
    check does not do so on everything, and that the label it certifies is the
    one an independent program reads off the generated structure.
    """
    group, site, k = case
    found = isotropy.candidates(group, site, k)
    assert len(found) > 0
    for candidate in found:
        assert candidate.verified is True, candidate.verification_reason
        assert candidate.bns_number == _spglib_bns(found, candidate), candidate.label


@pytest.mark.parametrize("plant", sorted(PLANTS))
@pytest.mark.parametrize("case", VERIFY_CASES, ids=[c[0] for c in VERIFY_CASES])
def test_verified_reads_the_operator_list(case, plant, monkeypatch):
    """Issue #607: a wrong operator list fails ``verified``, label by label.

    Before the fix ``in_allowed_span`` read only the direction's stabiliser and
    the permutation phases, never ``self.group``, so dropping the
    anti-translation sign relabelled all four MnO candidates (167.108 →
    166.101, 12.63 → 12.58, 15.90 → 12.62, 2.7 → 2.4) and reading the
    polar sign relabelled 22 of the 23 candidates here, with ``verified``
    True on every one.  Now every candidate whose plant changed its operator
    list fails, and the reason names an operation of that list.  The
    no-anti-translation plant changes nothing at k = 0 (there is no
    anti-translation to drop), and those candidates must stay verified.
    """
    group, site, k = case
    honest = {c.label: c.group.all_operations()
              for c in isotropy.candidates(group, site, k, verify=False)}
    monkeypatch.setattr(isotropy, "_candidate_group", PLANTS[plant])
    planted = isotropy.candidates(group, site, k, verify=False)
    changed = 0
    for candidate in planted:
        failure = candidate.verification_failure()
        if set(candidate.group.all_operations()) == set(honest[candidate.label]):
            assert failure is None, (candidate.label, failure)
            continue
        changed += 1
        assert not candidate.in_allowed_span(), candidate.label
        assert failure is not None and "own operator list" in failure, candidate.label
    if plant == "polar-for-axial" or k == HALF:
        assert changed == len(planted)
    else:
        assert changed == 0
    if changed == len(planted):
        with pytest.raises(RuntimeError, match="not fixed by its own operator list"):
            isotropy.candidates(group, site, k)


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
    from tests.test_magnetic_operators import not_a_group

    group = not_a_group()                # a list spglib cannot match at all
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
    assert ("proved 6 (absence 6, subspace 0, isometry 0, farkas 0, propagated 0, span 0, "
            "containment 0, transfer 0); sampled 0" in str(found))


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

    No family-level certificate separates them — their spans coincide to
    4e-15 both ways, and they are not isometric (issue #565 part 3's
    acceptance: S1 against S2 gets no isometry) — so every S1/S2 direction
    of the full twelve-family set is sampled or unresolved at one draw,
    never proved, whatever the draws say.  Two positive arms in the same
    set: S3 and S4 are dark at shells S1 and S2 light, so all 36 directions
    from an S1 or S2 family to an S3 or S4 one are proved; and the two
    rank-1 copies of each irrep *are* isometric, proved both ways with no
    draw.  One draw and one restart, since what is asserted is which
    verdicts the draws were *asked* for, not what they answered (19 s at
    restarts 4, most of it fits).
    """
    found = isotropy.candidates(*KNOWN_ANSWER)
    relations = isotropy.powder_relations(found, isotropy.reflections(found.lattice, 1.5),
                                          draws=1, restarts=1)
    irrep = [c.irrep_label for c in found]
    label = [c.label for c in found]
    between = [v for v in relations if {irrep[v.a], irrep[v.b]} == {"S1", "S2"}]
    assert len(between) == 18
    assert all(v.certificate not in ("absence", "subspace", "isometry") for v in between)
    assert any(v.status.startswith("sampled") and v.draws > 0 for v in between)
    across = [v for v in relations
              if irrep[v.a] in ("S1", "S2") and irrep[v.b] in ("S3", "S4")]
    assert len(across) == 36
    assert all(v.status == "proved-not" for v in across)
    copies = [v for v in relations if "(rank 1)" in label[v.a] and "(rank 1)" in label[v.b]
              and irrep[v.a] == irrep[v.b]]
    assert len(copies) == 8
    assert all((v.status, v.certificate, v.draws) == ("proved-contained", "isometry", 0)
               for v in copies)


def test_every_sampled_edge_prints_the_draws_it_actually_made(monkeypatch):
    """The n of every sampled pair is the number of draws that pair consumed, counted from outside.

    :func:`isotropy._normalised_draw` is wrapped to log which family each
    draw came from, and the log must be, draw for draw, the sequence the
    relations claim: each tested pair in order, a → b then b → a, ``draws``
    of each.  The printed n must be those numbers.  The set is six families
    of the cubic known-answer case (two S1 rank-1 copies and S1(a,b), two S2
    copies, one S3) at restarts 4, which holds sampled-contained directions
    (3 draws, within an irrep: S1(rank 1)#1 ↔ S1(a,b)), isometry-proved
    ones (the two rank-1 copies of S1 and of S2, nothing drawn), one
    Farkas-proved direction stopped early at its witness draw
    (S1(rank 1)#1 → S2(rank 1)#1 at draw 4 of 12 at this seed), the three
    S1 → S2 copy directions it is propagated to (nothing drawn), the
    S1(a,b) → S2 directions (drawn, since S1(a,b) has no isometric copy),
    unresolved and family-proved ones, so a count that ignored the early
    stop or charged a proved pair would show, and so would a draw spent on
    a pair already proved distinct, on a direction a propagated proof had
    settled, or on the other direction of a Farkas-proved one.  Before
    part 3 of issue #565 every S1 → S2 copy direction was drawn and
    certified on its own (2 to 4 draws each).
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#1", "S1(rank 1)#2", "S1(a,b)", "S2(rank 1)#1", "S2(rank 1)#2",
              "S3(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in labels))
    assert [c.label for c in subset] == labels
    log = []
    real = isotropy._normalised_draw

    def counting(candidate, lattice, rng):
        log.append(candidate.label)
        return real(candidate, lattice, rng)

    monkeypatch.setattr(isotropy, "_normalised_draw", counting)
    result = isotropy.analyse(subset, d_min=1.5, restarts=4)
    # the S1 class rests on the sampled S1(a,b) edge; S2's two copies are proved
    # equal and proved apart from every S1 family; S3 is proved apart from all
    assert _table_marks(result) == ["S", "S", "S", "P", "P", "P"]
    statuses = {v.status for v in result.relations}
    assert {"sampled-contained", "unresolved", "proved-not", "proved-contained"} <= statuses
    assert all((v.reason is not None) == (v.status == "unresolved") for v in result.relations)
    farkas = [v for v in result.relations if v.certificate == "farkas"]
    assert {(labels[v.a], labels[v.b]) for v in farkas} == {
        ("S1(rank 1)#1", "S2(rank 1)#1"), ("S1(a,b)", "S2(rank 1)#1")}
    assert all(0 < v.draws < isotropy.CROSS_IRREP_DRAWS for v in farkas)
    carried = [v for v in result.relations if v.certificate == "propagated"]
    assert {(labels[v.a], labels[v.b]) for v in carried} == {
        ("S1(rank 1)#1", "S2(rank 1)#2"), ("S1(rank 1)#2", "S2(rank 1)#1"),
        ("S1(rank 1)#2", "S2(rank 1)#2"), ("S1(a,b)", "S2(rank 1)#2")}
    assert all(v.status == "proved-not" and v.draws == 0 for v in carried)
    expected = []
    for (i, j), pair in _pairs(result.relations, len(subset)).items():
        for v in pair:
            other = pair[1] if v is pair[0] else pair[0]
            if v.certificate == "farkas":          # proved by a witness: its draw's index
                assert v.draws == v.witness.draw and v.undecided_draws == 0, v
                assert (other.status, other.reason, other.draws) == ("unresolved", "settled", 0)
            elif v.status == "proved-not":         # by a family certificate or carried: nothing drawn
                assert v.draws == other.draws == 0, pair
        for v in pair:
            expected += [labels[v.a]] * v.draws
            assert (v.draws > 0) == (v.status.startswith("sampled") or v.certificate == "farkas")
    assert log == expected
    proved_lines = [line for line in str(result).splitlines() if " ⊄ " in line]
    assert [line.split("  draw ")[1] for line in proved_lines if "  via " not in line] == \
        [str(v.draws) for v in farkas]
    assert sum("  via " in line for line in proved_lines) == len(carried)

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


def test_a_carried_proof_keeps_the_draws_of_the_direction_it_replaces(monkeypatch):
    """With the higher-index copy first in line for the proof, the lower-index copy's drawn direction is replaced and still counts its draws.

    The set is the draw-count test's, ordered ``[S1(rank 1)#2, S1(rank 1)#1,
    S1(a,b)... ]`` reduced to the case that matters: S1(rank 1)#2 → S2(a,b)
    is drawn first and ends without a proof, S1(rank 1)#1 → S2(a,b) is
    later proved by Farkas and carried to it.  The log of draws each family
    actually consumed must equal the sum of the printed ``draws``.
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#2", "S1(rank 1)#1", "S2(a,b)"]
    pick = {c.label: c for c in found}
    subset = replace(found, candidates=tuple(pick[name] for name in labels))
    log = []
    real = isotropy._normalised_draw

    def counting(candidate, lattice, rng):
        log.append(candidate.label)
        return real(candidate, lattice, rng)

    monkeypatch.setattr(isotropy, "_normalised_draw", counting)
    result = isotropy.analyse(subset, d_min=1.5, restarts=4)
    assert sum(v.draws for v in result.relations) == len(log)
    replaced = [v for v in result.relations
                if v.certificate == "propagated" and v.draws > 0]
    assert [(labels[v.a], labels[v.b]) for v in replaced] == [("S1(rank 1)#2", "S2(a,b)")]
    assert replaced[0].status == "proved-not" and replaced[0].via == (1, 2)


def test_the_default_draws_are_twelve_across_irreps_and_three_within(monkeypatch):
    """Issue #565's decision 3: 12 draws per direction between irreps, 3 inside one; a number overrides both.

    Every fit is replaced by a perfect reproduction, so each sampled
    direction runs its whole budget and ``draws`` *is* the budget.  The set
    is the draw-count test's six cubic families: S1 → S2 pairs are across
    irreps, S1(rank 1) → S1(a,b) inside one (the two rank-1 copies of an
    irrep are isometric since part 3 of issue #565, proved and not drawn,
    so the within-irrep budget is read off the direction against the (a,b)
    plane), and S3 is proved apart, so it is never drawn.
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#1", "S1(rank 1)#2", "S1(a,b)", "S2(rank 1)#1", "S2(rank 1)#2",
              "S3(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in labels))
    reflections = isotropy.reflections(found.lattice, 1.5)
    monkeypatch.setattr(isotropy, "_certify_draw",
                        lambda *args, **kwargs: (True, False, None, None))
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
    default 12 across irreps some draw of every such pair is not.  The
    classes are a sampled verdict at one seed (20260906), so this pins the
    protocol.  Since part 2 of issue #565 the separations are proved: of
    the 54 cross-irrep pairs, 36 by absence (S1/S2 against S3/S4) and 18
    by a Farkas witness, found on the pair or carried to it from an
    isometric copy (part 3: the rank-1 copies of each irrep are proved
    equal, so a witness against one is a witness against the other), each
    re-verified here from its t and y against the pair's own stack.  Before
    part 3 the 18th, S1(rank 1)#2 → S2(a,b), was ``sampled-not`` with a
    negative dual (no certificate exists for *its* draw); the proof it
    carries now is S1(rank 1)#1 → S2(a,b)'s.  The witnesses' d_lo run from
    0.0013 to 0.032.  50-200 s on one core by machine load and tree, hence
    slow.
    """
    found = isotropy.analyse(isotropy.candidates(*KNOWN_ANSWER), d_min=1.5)
    by_irrep = {}
    for i, candidate in enumerate(found):
        by_irrep.setdefault(candidate.irrep_label, []).append(i)
    assert found.classes == tuple(tuple(members) for members in by_irrep.values())
    assert len(found.classes) == 4

    irrep = [c.irrep_label for c in found]
    label = [c.label for c in found]
    cross = [pair for (i, j), pair in _pairs(found.relations, len(found)).items()
             if irrep[i] != irrep[j]]
    assert len(cross) == 54
    by = {}
    for pair in cross:
        proof = next((v.certificate for v in pair if v.status == "proved-not"), None)
        by[proof] = by.get(proof, 0) + 1
    assert by["absence"] == 36 and by["farkas"] + by["propagated"] == 18 and None not in by
    assert by["farkas"] >= 4             # one found draw per (S1 family, S2 family-or-copy class) at least
    assert not [v for v in found.relations if v.status == "sampled-not"]
    # part 4: each rank-1 copy is proved inside its (a,b) plane (8 directions), and no
    # transfer has anything left to carry, every cross-irrep direction being proved already
    spans = [v for v in found.relations if v.certificate == "span"]
    assert len(spans) == 8 and all(v.containment.residual <= 1e-12 for v in spans)
    assert {(label[v.a].split("(")[0], "(rank 1)" in label[v.a], label[v.b].endswith("(a,b)"))
            for v in spans} == {(s, True, True) for s in ("S1", "S2", "S3", "S4")}
    assert not [v for v in found.relations if v.certificate in ("containment", "transfer")]
    copies = [v for v in found.relations if v.certificate == "isometry"]
    assert {(label[v.a], label[v.b]) for v in copies} == {
        (f"{s}(rank 1)#{p}", f"{s}(rank 1)#{q}") for s in ("S1", "S2", "S3", "S4")
        for p, q in ((1, 2), (2, 1))}
    reflections = isotropy.reflections(found.lattice, 1.5)
    canonical = [isotropy._canonical_basis(c) for c in found]
    grams = {}
    proved = [v for v in found.relations if v.certificate in ("farkas", "propagated")]
    assert all(v.status == "proved-not" and v.witness is not None for v in proved)
    for v in proved:
        if v.b not in grams:
            grams[v.b] = isotropy.gram(isotropy.structure_factors(canonical[v.b], reflections),
                                       reflections.shells)
        assert isotropy._verify_witness(grams[v.b], v.witness)[0], v
        assert v.d[0] <= v.d[1]
        if v.certificate == "propagated":
            source = next(s for s in proved if (s.a, s.b) == v.via)
            assert source.certificate == "farkas" and v.witness is source.witness
            assert irrep[source.a] == irrep[v.a] and irrep[source.b] == irrep[v.b]
    assert 1e-3 < min(v.d[0] for v in proved) and max(v.d[0] for v in proved) < 0.05


def test_the_certificates_run_on_a_pair_union_find_has_already_joined(monkeypatch):
    """A join is transitive and a proof is not, so a joined pair still gets its certificates.

    The draw-count test's six cubic families, every fit replaced by a
    perfect reproduction, so S1 ∪ S2 is one class.  The positive arm: the
    certificates of S1(a,b) ↔ S3 are withheld, so that pair is drawn and
    joined, and S3 joins the class through it — as a later certificate
    that is not an equivalence (a stored Farkas witness, issue #565 part 2)
    can leave a proved separation inside a class.  Every other S3 pair is
    then reached already joined, and must still carry its ``proved-not``;
    the S1/S2 pairs reached joined carry ``reason="joined"`` and no draws.
    The withheld partner is S1(a,b) and not, as before part 3, a rank-1
    copy: withholding S1(rank 1)#1 ↔ S3 no longer opens the pair, because
    S1(rank 1)#1 ≅ S1(rank 1)#2 and S1(rank 1)#2 ⊄ S3 by absence, so the
    proof is carried (``propagated``) and S3 stays apart — the second
    arm below.
    """
    from dataclasses import replace

    found = isotropy.candidates(*KNOWN_ANSWER)
    labels = ["S1(rank 1)#1", "S1(rank 1)#2", "S1(a,b)", "S2(rank 1)#1", "S2(rank 1)#2",
              "S3(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in labels))
    reflections = isotropy.reflections(found.lattice, 1.5)
    monkeypatch.setattr(isotropy, "_certify_draw",
                        lambda *args, **kwargs: (True, False, None, None))
    real = isotropy._certify

    def withheld(a, b, *args):
        return None if {a, b} == {2, 5} else real(a, b, *args)

    monkeypatch.setattr(isotropy, "_certify", withheld)
    classes, relations = isotropy._classify(subset, reflections, draws=3,
                                            seed=20260906, rtol=1e-4, restarts=1)
    assert classes == ((0, 1, 2, 3, 4, 5),)
    pairs = _pairs(relations, len(subset))
    for (i, j), pair in pairs.items():
        if 5 in (i, j) and 2 not in (i, j):
            assert any(v.status == "proved-not" and v.certificate is not None
                       for v in pair), pair
            assert all(v.draws == 0 for v in pair), pair
    joined = [v for v in relations if v.reason == "joined"]
    assert joined
    assert all(v.draws == 0 and v.status == "unresolved" for v in joined)
    assert all(5 not in (v.a, v.b) for v in joined)

    def withheld_copy(a, b, *args):
        return None if {a, b} == {0, 5} else real(a, b, *args)

    monkeypatch.setattr(isotropy, "_certify", withheld_copy)
    classes, relations = isotropy._classify(subset, reflections, draws=3,
                                            seed=20260906, rtol=1e-4, restarts=1)
    assert classes == ((0, 1, 2, 3, 4), (5,))
    verdicts = {(v.a, v.b): v for v in relations}
    carried = verdicts[(0, 5)]
    assert (carried.status, carried.certificate, carried.via, carried.draws) == \
        ("proved-not", "propagated", (1, 5), 0)
    assert verdicts[(1, 5)].certificate == "absence"
    assert (verdicts[(5, 0)].status, verdicts[(5, 0)].reason) == ("unresolved", "settled")


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


# --------------------------------------------------------------------------
# I. The Farkas certificate of one draw (issue #565, part 2)
# --------------------------------------------------------------------------

#: Three shells of two amplitudes: I(x) = (x₁², x₂², (x₁ + x₂)²/2).  Its
#: relaxed cone is {(X₁₁, X₂₂, (X₁₁ + X₂₂ + 2X₁₂)/2) : X ⪰ 0}, so t = (1, 1, 2.5)
#: needs X₁₂ = 1.5 > √(X₁₁X₂₂) and is out of reach, while (1, 1, 1.5) is in it.
#: The nearest point of the cone to (1, 1, 2.5) is symmetric (the projection
#: onto a convex set is unique, and the swap x₁ ↔ x₂ fixes both), so it is on
#: the ray (1, 1, 2): residual √3/6, relative distance √3/6/√8.25 = 0.10050.
SYNTHETIC_STACK = np.array([np.diag([1.0, 0.0]), np.diag([0.0, 1.0]),
                            0.5 * np.ones((2, 2))])
SYNTHETIC_OUT = np.array([1.0, 1.0, 2.5])
SYNTHETIC_IN = np.array([1.0, 1.0, 1.5])
SYNTHETIC_DISTANCE = np.sqrt(3.0) / 6.0 / np.sqrt(8.25)


def _unit(t):
    return t / np.linalg.norm(t)


def test_the_householder_basis_is_orthonormal_and_orthogonal_to_the_target():
    """Columns 2… of one reflector span t̂⊥, for any sign of t̂'s first entry; no SVD is needed."""
    rng = np.random.default_rng(1)
    vectors = [np.eye(5)[0], -np.eye(5)[0], np.eye(5)[3], _unit(rng.normal(size=7)),
               _unit(np.abs(rng.normal(size=21)))]
    for u in vectors:
        basis = isotropy._householder_complement(u)
        assert basis.shape == (u.shape[0], u.shape[0] - 1)
        assert np.allclose(basis.T @ basis, np.eye(u.shape[0] - 1), atol=1e-14)
        assert float(np.max(np.abs(basis.T @ u))) <= 1e-14
    assert isotropy._householder_complement(np.array([1.0])).shape == (1, 0)


def test_the_exact_check_refuses_what_the_float_eigenvalue_cannot_see():
    """[[1, 1], [1, 1 − 2⁻⁵³]] has a float eigenvalue at round-off and determinant −2⁻⁵³ exactly.

    The float spectrum cannot say which side of zero it is on; the rational
    LDLᵀ can, and refuses it.  The positive arms: [[1, 1], [1, 1]] (a zero
    pivot with a zero row, PSD) and a strictly positive matrix; and a
    negated PSD matrix is refused.
    """
    almost = np.array([[[1.0, 1.0], [1.0, 1.0 - 2.0 ** -53]]])
    assert 1.0 - 2.0 ** -53 != 1.0
    assert abs(float(np.linalg.eigvalsh(almost[0])[0])) <= 1e-15
    assert not isotropy._exact_psd(almost, [1.0])
    assert isotropy._exact_psd(np.array([np.ones((2, 2))]), [1.0])
    assert isotropy._exact_psd(np.array([[[2.0, 1.0], [1.0, 2.0]]]), [1.0])
    assert not isotropy._exact_psd(np.array([[[2.0, 1.0], [1.0, 2.0]]]), [-1.0])


def test_the_kernel_projection_finds_the_common_kernel_and_guards_its_residual():
    """A zero direction shared by every block is projected out; a near-kernel one coupled to the rest is flagged.

    The synthetic stack padded with a zero amplitude has a one-dimensional
    common kernel at residual 0, and the projected stack is the original.
    The guard's positive arm: G₁ = vvᵀ with v = (1, 10⁻⁶) beside G₂ = e₁e₁ᵀ
    puts Σ G_s's small eigenvalue at 2.5e-13 of the largest, inside the cut,
    while G₁ moves that direction by 5e-7 of its norm, above
    :data:`isotropy.INTENSITY_RTOL`: no certificate may be built on it.
    """
    padded = np.zeros((3, 3, 3))
    padded[:, :2, :2] = SYNTHETIC_STACK
    projected, kernel, residual = isotropy._live_projection(padded)
    assert (kernel, residual) == (1, 0.0)
    assert projected.shape == (3, 2, 2)
    plain, none, _ = isotropy._live_projection(SYNTHETIC_STACK)
    assert none == 0
    assert np.allclose(np.linalg.eigvalsh(np.einsum("s,sij->ij", [1.0, 2.0, 3.0], projected)),
                       np.linalg.eigvalsh(np.einsum("s,sij->ij", [1.0, 2.0, 3.0], plain)),
                       atol=1e-14)

    v = np.array([1.0, 1e-6])
    coupled = np.array([np.outer(v, v), np.diag([1.0, 0.0])])
    _, kernel, residual = isotropy._live_projection(coupled)
    assert kernel == 1 and residual > 100 * isotropy.INTENSITY_RTOL
    assert isotropy._farkas_certificate(coupled, np.array([1.0, 1.5])) == (None, None)


def test_the_synthetic_certificate_brackets_the_known_distance():
    """Dual, minimum norm, quote and exact check on a stack whose distance is known in closed form.

    Out of reach: the dual clears :data:`isotropy.FARKAS_FLOOR`, the quoted y
    keeps y·t̂ = −1, is PSD in exact arithmetic with ratio ≥
    :data:`isotropy.FARKAS_QUOTE`, and 1/‖y‖ is a lower bound within 1 % of
    the closed-form 0.10050 (the minimum-norm point gives it exactly; the
    quote steps inside).  In reach: the dual is negative and nothing is
    issued.  With a zero amplitude padded on, the unprojected dual sits on
    the structural zero and is refused, the projected one accepted.
    """
    t_hat = _unit(SYNTHETIC_OUT)
    dual, y_dual = isotropy._farkas_dual(SYNTHETIC_STACK / 1.0, t_hat)
    assert dual >= isotropy.FARKAS_FLOOR
    # the maximiser itself drifts: λ_min grows without bound along a z ⊥ t̂ with
    # M(z) ≻ 0, so ‖y‖ is huge and y·t̂ = −1 is lost to cancellation; it is
    # never quoted, only used to aim the minimum-norm solve
    assert np.linalg.norm(y_dual) > 1e6
    y_mn, anchor = isotropy._min_norm_certificate(SYNTHETIC_STACK, t_hat, y_dual)
    assert 1.0 / np.linalg.norm(y_mn) == pytest.approx(SYNTHETIC_DISTANCE, rel=1e-4)
    assert np.linalg.norm(anchor) > np.linalg.norm(y_mn)
    y = isotropy._quote_inside(SYNTHETIC_STACK, y_mn, anchor)
    assert isotropy._spectrum_ratio(SYNTHETIC_STACK, y) >= isotropy.FARKAS_QUOTE
    assert isotropy._exact_psd(SYNTHETIC_STACK, y)
    assert abs(float(y @ t_hat) + 1.0) <= 1e-12
    d_lo = 1.0 / float(np.linalg.norm(y))
    assert SYNTHETIC_DISTANCE * 0.99 <= d_lo <= SYNTHETIC_DISTANCE * (1 + 1e-12)

    dual, parts = isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_OUT)
    assert parts is not None and parts["exact"] and parts["kernel_dim"] == 0
    assert parts["rounding_bound"] < 1e-13
    assert isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_IN)[1] is None
    assert isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_IN)[0] < 0.0

    padded = np.zeros((3, 3, 3))
    padded[:, :2, :2] = SYNTHETIC_STACK
    raw, _ = isotropy._farkas_dual(padded, t_hat)
    assert raw < isotropy.FARKAS_FLOOR and abs(raw) <= 1e-15
    dual, parts = isotropy._farkas_certificate(padded, SYNTHETIC_OUT)
    assert parts is not None and parts["kernel_dim"] == 1
    assert 1.0 / np.linalg.norm(parts["y"]) == pytest.approx(d_lo, rel=1e-6)


def test_a_stored_synthetic_witness_reverifies_and_its_negation_does_not():
    """:func:`isotropy._verify_witness` rebuilds the stack from t and live alone; −y and another stack fail."""
    _, parts = isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_OUT)
    y = parts["y"]
    witness = isotropy.Witness(
        draw=1, t=tuple(SYNTHETIC_OUT), live=(0, 1, 2), y=tuple(y), weights=None,
        kernel_dim=0, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"),
        ratio=parts["ratio"], rounding_bound=parts["rounding_bound"], exact=True,
        d=(1.0 / float(np.linalg.norm(y)), 1.0),
        interior=tuple(parts["interior"]), margin=parts["margin"])
    assert parts["kernel_amplitude_ratio"] == float("inf")
    holds, ratio, off = isotropy._verify_witness(SYNTHETIC_STACK, witness)
    assert holds and ratio >= isotropy.FARKAS_FLOOR and off <= 1e-12
    from dataclasses import replace

    assert not isotropy._verify_witness(SYNTHETIC_STACK, replace(witness, y=tuple(-y)))[0]
    # the interior direction is checked too: its negation bounds nothing, and it must be unit
    assert not isotropy._verify_witness(
        SYNTHETIC_STACK, replace(witness, interior=tuple(-v for v in witness.interior)))[0]
    assert not isotropy._verify_witness(
        SYNTHETIC_STACK, replace(witness, interior=tuple(2.0 * v for v in witness.interior)))[0]
    assert 0.0 < witness.margin <= 1.0
    # a stack that reaches t = (1, 1, 2.5) at x = (1, 1): no certificate exists for it
    other = np.array([np.diag([1.0, 0.0]), np.diag([0.0, 1.0]), 1.25 * np.eye(2)])
    assert not isotropy._verify_witness(other, witness)[0]
    # a witness is hashable, as the frozen PairVerdict it rides on must be
    assert hash(isotropy.PairVerdict(0, 1, "proved-not", "farkas", 1, 0, d=witness.d,
                                     witness=witness, dual=0.1))


#: ``P m -3 m`` at (0, 0, ½), general site: 14 families, eight of them with a
#: common kernel on their live shells (S5(a), S8(a) and the six S9/S10).
PM3M_X = ("P m -3 m", P21C_SITE, P21C_K)


def _stack(case):
    found = isotropy.candidates(*case)
    reflections = isotropy.reflections(found.lattice, 1.5)
    canonical = [isotropy._canonical_basis(c) for c in found]
    factors = [isotropy.structure_factors(c, reflections) for c in canonical]
    grams = [isotropy.gram(f, reflections.shells) for f in factors]
    dark = [isotropy._certificate_dark(g, isotropy._silent(f))
            for g, f in zip(grams, factors)]
    labels = [c.label for c in found]
    return found, reflections, canonical, grams, dark, labels


@pytest.fixture(scope="module")
def known_answer_stack():
    """The known answer's candidates, canonical bases, Gram stacks and dark shells, built once (about 1.5 s)."""
    return _stack(KNOWN_ANSWER)


@pytest.fixture(scope="module")
def pm3mx_stack():
    """``PM3M_X``'s candidates, canonical bases, Gram stacks and dark shells, built once (about 1.5 s)."""
    return _stack(PM3M_X)


def _own_draws(stack, label, n):
    """n draws of one family against its own stack: (target, live, live stack) each."""
    found, reflections, canonical, grams, dark, labels = stack
    b = labels.index(label)
    rng = np.random.default_rng(20260906)
    out = []
    for _ in range(n):
        x = isotropy._normalised_draw(canonical[b], reflections.lattice, rng)
        t = (grams[b] @ x) @ x
        live = isotropy._fit_rows(t, grams[b]) & ~dark[b]
        out.append((t, live, grams[b][live]))
    return out


@pytest.mark.xdist_group("magnetic-pm3mx")
def test_a_draw_of_a_kernel_family_never_certifies_against_itself(pm3mx_stack):
    """A family reproduces its own draws, so no certificate may exist for them, projected or not.

    ``P m -3 m`` at (0, 0, ½): S5(a) and S8(a) each have a one-dimensional
    common kernel on their live shells.  Three own draws each: the projected
    dual and the unprojected one are both strictly negative, and nothing is
    issued.  The positive arm is the next test, a cross-family draw on the
    same kind of stack that certifies.
    """
    for label in ("S5(a)", "S8(a)"):
        for t, live, g in _own_draws(pm3mx_stack, label, 3):
            assert isotropy._live_projection(g)[1] == 1
            dual, parts = isotropy._farkas_certificate(g, t[live])
            raw, _ = isotropy._farkas_dual(g / np.max(np.abs(g)), _unit(t[live]))
            assert parts is None and dual < 0.0 and raw < 0.0, (label, dual, raw)


@pytest.mark.xdist_group("magnetic-known-answer")
def test_a_draw_of_the_known_answer_never_certifies_against_itself(known_answer_stack):
    """The same negative arm on a family with no kernel: S2(rank 1)#1 against its own draws."""
    for t, live, g in _own_draws(known_answer_stack, "S2(rank 1)#1", 3):
        assert isotropy._live_projection(g)[1] == 0
        dual, parts = isotropy._farkas_certificate(g, t[live])
        assert parts is None and dual < 0.0, dual


@pytest.mark.xdist_group("magnetic-pm3mx")
def test_a_kernel_family_is_certified_only_once_its_kernel_is_projected_out(pm3mx_stack):
    """S1(a) → S5(a): on the raw stack the dual sits on the structural zero; projected, it certifies.

    The first draw of the pair's stream.  S5(a)'s stack has a common kernel
    of dimension 1, so every Σ y_s G_s has a zero eigenvalue and the raw
    dual's ratio is round-off (2e-17 here), below the floor; with the kernel
    projected out the optimum is 1.1e-6 and the certificate gives
    d_lo = 0.0055, above the gate (2.3e-4 at ``rtol`` 1e-4).  The unit test
    of :func:`isotropy._live_projection` holds the guard that refuses a
    kernel whose residual is above :data:`isotropy.INTENSITY_RTOL`.
    """
    found, reflections, canonical, grams, dark, labels = pm3mx_stack
    a, b = labels.index("S1(a)"), labels.index("S5(a)")
    x = isotropy._normalised_draw(canonical[a], reflections.lattice,
                                  np.random.default_rng(20260906))
    t = (grams[a] @ x) @ x
    live = isotropy._fit_rows(t, grams[b]) & ~dark[b]
    g = grams[b][live]
    raw, _ = isotropy._farkas_dual(g / np.max(np.abs(g)), _unit(t[live]))
    assert abs(raw) <= 1e-15
    dual, parts = isotropy._farkas_certificate(g, t[live])
    assert dual >= 1e-7 and parts is not None and parts["kernel_dim"] == 1
    assert parts["kernel_residual"] <= 1e-12
    d_lo = 1.0 / float(np.linalg.norm(parts["y"]))
    assert d_lo == pytest.approx(0.0055, rel=0.05)
    assert d_lo >= isotropy._gate(1e-4, t, live)


@pytest.mark.xdist_group("magnetic-pm3mx")
def test_the_gate_reads_rtol_with_the_root_s_factor(monkeypatch, pm3mx_stack):
    """A certificate proves a draw out of reach at ``rtol`` only when d_lo ≥ rtol·√S·max|t|/‖t‖.

    The T3 draw (S1(a) → S5(a)) with every restart stubbed to fail, so the
    certificate alone decides.  At ``rtol`` 1e-4 and 1e-9 it proves the
    draw, after exactly one restart call; at an ``rtol`` between
    d_lo·‖t‖/(√S·max|t|) and d_lo it does not (a gate without the √S factor
    would), the witness rides along and the remaining restarts run.  Here
    √S·max|t|/‖t‖ = 2.3.
    """
    found, reflections, canonical, grams, dark, labels = pm3mx_stack
    a, b = labels.index("S1(a)"), labels.index("S5(a)")
    x = isotropy._normalised_draw(canonical[a], reflections.lattice,
                                  np.random.default_rng(20260906))
    t = (grams[a] @ x) @ x
    calls = []

    def failing(*args, **kwargs):
        calls.append(kwargs["restarts"])
        return 1.0, 1.0, np.zeros(grams[b].shape[1])

    monkeypatch.setattr(isotropy, "_restarts", failing)

    def run(rtol):
        calls.clear()
        return isotropy._certify_draw(t, grams[b], dark[b], np.random.default_rng(0),
                                      restarts=8, rtol=rtol, draw=1)

    reproduced, certified, witness, dual = run(1e-4)
    assert (reproduced, certified, calls) == (False, True, [1])
    d_lo = witness.d[0]
    factor = isotropy._gate(1.0, t, np.isin(np.arange(len(t)), witness.live))
    assert 1.5 < factor < 4.0
    middle = d_lo / np.sqrt(factor)          # inside (d_lo/factor, d_lo)
    reproduced, certified, witness, dual = run(middle)
    assert (reproduced, certified, calls) == (False, False, [1, 7])
    assert witness is not None and witness.d[0] == pytest.approx(d_lo)
    assert run(1e-9)[1]


@pytest.mark.xdist_group("magnetic-known-answer")
def test_a_proved_separation_inside_a_joined_class_is_reported(monkeypatch, known_answer_stack):
    """Union-find can join two families a witness has proved apart; the table must say so.

    Three known-answer families, every draw stubbed to be reproduced except
    those of S1(rank 1)#1 → S2(rank 1)#1, which run for real and certify at
    draw 4 at this seed (20260906).  S2(rank 1)#1 then joins the class
    through the stubbed S1(a,b) pair, so one class holds a
    ``proved-not``/``farkas`` direction: it is marked S, the separation is
    printed with its d bracket, and the class is named as holding one.
    This is the shape ``F -4 3 m`` Γ takes at seed 2 (S4 ⊄ S5 inside
    S4 ∪ S5).  The joining family is S1(a,b) rather than part 2's
    S1(rank 1)#2, because a rank-1 copy is isometric to S1(rank 1)#1 since
    part 3 and inherits its proof, which closes the join this test is
    about; S1(a,b) has no isometric copy.  Since part 4 the join is
    narrower still: S1(rank 1)#1 ⊆ S1(a,b) is proved (``span``), so the
    witness is carried to S1(a,b) ⊄ S2(rank 1)#1 (``containment``, issue
    #565 item 5, the first rule) over the stubbed draws that had joined
    that direction, which keep their count; the class is held by the two
    remaining sampled directions and is still marked S.
    """
    from dataclasses import replace

    found, reflections, canonical, grams, dark, labels = known_answer_stack
    names = ["S1(rank 1)#1", "S1(a,b)", "S2(rank 1)#1"]
    subset = replace(found, candidates=tuple(c for c in found if c.label in names))
    target = grams[labels.index("S2(rank 1)#1")]
    drawn = []
    real_draw, real_certify = isotropy._normalised_draw, isotropy._certify_draw

    def logging(candidate, lattice, rng):
        drawn.append(candidate.label)
        return real_draw(candidate, lattice, rng)

    def selective(t, grams_b, *args, **kwargs):
        if drawn[-1] == "S1(rank 1)#1" and np.array_equal(grams_b, target):
            return real_certify(t, grams_b, *args, **kwargs)
        return True, False, None, None

    monkeypatch.setattr(isotropy, "_normalised_draw", logging)
    monkeypatch.setattr(isotropy, "_certify_draw", selective)
    result = isotropy.analyse(subset, d_min=1.5, restarts=4)
    assert result.classes == ((0, 1, 2),)
    assert _table_marks(result) == ["S"] * 3
    there = next(v for v in result.relations if (v.a, v.b) == (0, 2))
    assert (there.status, there.certificate, there.draws) == ("proved-not", "farkas", 4)
    lo, hi = there.d
    text = str(result)
    assert f"S1(rank 1)#1 ⊄ S2(rank 1)#1  d ∈ [{lo:.2g}, {hi:.2g}]  draw 4" in text
    assert "classes holding a proved separation (part 5 of issue #565 splits them): 0" in text
    assert ("proved 2 (absence 0, subspace 0, isometry 0, farkas 1, propagated 0, span 0, "
            "containment 1, transfer 0)") in text
    verdicts = {(v.a, v.b): v for v in result.relations}
    assert (verdicts[(0, 1)].status, verdicts[(0, 1)].certificate) == ("proved-contained", "span")
    carried = verdicts[(1, 2)]
    assert (carried.status, carried.certificate, carried.via, carried.draws) == \
        ("proved-not", "containment", (0, 2), isotropy.CROSS_IRREP_DRAWS)
    assert carried.witness is there.witness and carried.d == there.d
    assert f"  S1(a,b) ⊄ S2(rank 1)#1  via S1(rank 1)#1 ⊄ S2(rank 1)#1  d ∈ [{lo:.2g}, {hi:.2g}]" in text
    assert {v.status for v in (verdicts[(1, 0)], verdicts[(2, 1)])} == {"sampled-contained"}


@pytest.mark.xdist_group("magnetic-known-answer")
def test_a_separation_proved_on_one_copy_appears_on_the_other(known_answer_stack):
    """S1 against S2 of the known answer at restarts 4: every S1 → S2 direction is proved, four by a found witness and five by propagation.

    The six S1 and S2 families.  The two rank-1 copies of each irrep are
    isometric, so the pair loop draws one direction per (S1 copy class or
    S1(a,b)) × (S2 copy class or S2(a,b)) and carries the proof to the
    copies: at seed 20260906 the four drawn directions certify (pinned
    below, with the draw each stops at), and the five others are
    ``propagated`` with ``via`` naming the source, ``draws`` 0 and the
    source's witness.  Issue #565 part 3's acceptance row: the two
    directions part 2 left ``sampled-not`` with a negative dual
    (S1(rank 1)#2 → S2(a,b) and S1(a,b) → S2(rank 1)#2, whose own draws
    have no certificate) are now proved by the copy's witness.  Every
    witness, found or carried, is re-verified from its stored t and y
    against the *target's own* stack (a carried one against the copy's,
    which the congruence makes valid), sits at ratio ≥
    :data:`isotropy.FARKAS_QUOTE`, passes the exact check, has
    d_lo ≤ d_up and clears the gate.  No physical floor: the smallest d_lo
    is 0.0071, below the 1e-2 a floor might be tempted to set.  Part 2
    drew all nine directions here (56.7 s at review); this draws four.
    """
    from dataclasses import replace

    found, reflections, canonical, grams, dark, labels = known_answer_stack
    subset = replace(found, candidates=tuple(c for c in found if c.irrep_label in ("S1", "S2")))
    names = [c.label for c in subset]
    classes, relations = isotropy._classify(subset, reflections, draws=None, seed=20260906,
                                            rtol=1e-4, restarts=4)
    result = replace(subset, classes=classes, relations=relations)
    assert classes == ((0, 1, 2), (3, 4, 5))
    farkas = {(names[v.a], names[v.b]): v for v in result.relations if v.certificate == "farkas"}
    assert {key: v.draws for key, v in farkas.items()} == {
        ("S1(rank 1)#1", "S2(rank 1)#1"): 4, ("S1(rank 1)#1", "S2(a,b)"): 3,
        ("S1(a,b)", "S2(rank 1)#1"): 4, ("S1(a,b)", "S2(a,b)"): 3}
    carried = {(names[v.a], names[v.b]): v for v in result.relations
               if v.certificate == "propagated"}
    assert {key: (names[v.via[0]], names[v.via[1]]) for key, v in carried.items()} == {
        ("S1(rank 1)#1", "S2(rank 1)#2"): ("S1(rank 1)#1", "S2(rank 1)#1"),
        ("S1(rank 1)#2", "S2(rank 1)#1"): ("S1(rank 1)#1", "S2(rank 1)#1"),
        ("S1(rank 1)#2", "S2(rank 1)#2"): ("S1(rank 1)#1", "S2(rank 1)#1"),
        ("S1(rank 1)#2", "S2(a,b)"): ("S1(rank 1)#1", "S2(a,b)"),
        ("S1(a,b)", "S2(rank 1)#2"): ("S1(a,b)", "S2(rank 1)#1")}
    assert all(v.status == "proved-not" and v.draws == 0 for v in carried.values())
    assert not [v for v in result.relations if v.status == "sampled-not"]
    irrep = {c.label: c.irrep_label for c in subset}
    assert all(v.status == "proved-not" for v in result.relations
               if irrep[names[v.a]] == "S1" and irrep[names[v.b]] == "S2")
    isometric = {(names[v.a], names[v.b]) for v in result.relations
                 if v.certificate == "isometry"}
    assert isometric == {("S1(rank 1)#1", "S1(rank 1)#2"), ("S1(rank 1)#2", "S1(rank 1)#1"),
                         ("S2(rank 1)#1", "S2(rank 1)#2"), ("S2(rank 1)#2", "S2(rank 1)#1")}
    for (a, b), v in {**farkas, **carried}.items():
        w = v.witness
        holds, ratio, off = isotropy._verify_witness(grams[labels.index(b)], w)
        assert holds and off <= 1e-9 and ratio >= isotropy.FARKAS_FLOOR, (a, b)
        assert w.exact and w.ratio >= isotropy.FARKAS_QUOTE and w.rounding_bound < 1e-13
        assert w.kernel_amplitude_ratio == float("inf") and w.kernel_dim == 0
        assert v.d == w.d and w.d[0] == pytest.approx(1.0 / np.linalg.norm(w.y))
        assert w.d[0] <= w.d[1]
        live = np.isin(np.arange(len(w.t)), w.live)
        assert w.d[0] >= isotropy._gate(1e-4, np.asarray(w.t), live)
        assert v.dual >= isotropy.FARKAS_FLOOR
    for key, v in carried.items():
        assert v.witness is farkas[(names[v.via[0]], names[v.via[1]])].witness
    assert min(v.d[0] for v in farkas.values()) < 1e-2
    printed = [line for line in str(result).splitlines() if " ⊄ " in line]
    assert len(printed) == len(farkas) + len(carried)
    assert sum(" via " in line for line in printed) == len(carried)
    for line in printed:
        lo, hi = (float(x) for x in line.split("d ∈ [")[1].split("]")[0].split(", "))
        assert lo <= hi


def _known_pair(known_answer_stack, names=("S1(rank 1)#2", "S2(rank 1)#1")):
    from dataclasses import replace

    found = known_answer_stack[0]
    return replace(found, candidates=tuple(c for c in found if c.label in names))


@pytest.mark.xdist_group("magnetic-known-answer")
def test_the_exact_check_is_called_once_per_witness_and_refuses_on_false(monkeypatch,
                                                                         known_answer_stack):
    """The exact LDLᵀ is the arbiter: it runs on every quoted certificate, and a False issues no witness.

    S1(rank 1)#2 → S2(rank 1)#1, which certifies at draw 2 (seed 20260906,
    restarts 4).  A spy counts one exact call per witness issued.  With the
    exact check forced False the same draw is not certified: no witness,
    no ``farkas``, and the draws decide (here the draw is not reproduced in
    4 restarts, so ``sampled-not`` with the dual's positive optimum, a
    certificate the arbiter refused).  The unit test of
    :func:`isotropy._exact_psd` holds what it refuses on its own.
    """
    subset = _known_pair(known_answer_stack)
    reflections = known_answer_stack[1]
    calls = []
    real = isotropy._exact_psd

    def spy(*args):
        calls.append(1)
        return real(*args)

    monkeypatch.setattr(isotropy, "_exact_psd", spy)
    relations = isotropy.powder_relations(subset, reflections, restarts=4)
    witnesses = [v.witness for v in relations if v.witness is not None]
    assert len(witnesses) == len(calls) == 1
    assert relations[0].certificate == "farkas" and relations[0].draws == 2

    monkeypatch.setattr(isotropy, "_exact_psd", lambda *args: False)
    refused = isotropy.powder_relations(subset, reflections, restarts=4)
    assert all(v.witness is None and v.certificate is None for v in refused)
    assert (refused[0].status, refused[0].draws) == ("sampled-not", 2)
    assert refused[0].dual >= isotropy.FARKAS_FLOOR


@pytest.mark.xdist_group("magnetic-known-answer")
def test_weights_move_d_and_not_what_is_proved(known_answer_stack):
    """Per-shell weights change the norm d is measured in; the statuses stay the draws' and the gate's.

    S1(rank 1)#2 → S2(rank 1)#1 at restarts 4.  Uniform weights of 2 leave
    every status and d unchanged to 1e-9 (d is a relative distance); a ramp
    from 0.25 to 4 across the shells leaves every status unchanged, moves
    d, and is recorded on the witness.  A wrong length or a zero weight is
    refused by name.
    """
    subset = _known_pair(known_answer_stack)
    reflections = known_answer_stack[1]
    n_shells = len(reflections.shells)
    plain = isotropy.powder_relations(subset, reflections, restarts=4)
    doubled = isotropy.powder_relations(subset, reflections, restarts=4,
                                        weights=2.0 * np.ones(n_shells))
    ramp = np.geomspace(0.25, 4.0, n_shells)
    ramped = isotropy.powder_relations(subset, reflections, restarts=4, weights=ramp)
    assert [v.status for v in plain] == [v.status for v in doubled] == [v.status for v in ramped]
    assert plain[0].certificate == "farkas"
    assert np.allclose(doubled[0].d, plain[0].d, rtol=1e-9, atol=0.0)
    assert doubled[0].witness.weights == (2.0,) * n_shells
    assert ramped[0].witness.weights == tuple(ramp)
    assert abs(ramped[0].d[0] / plain[0].d[0] - 1.0) > 1e-2
    assert isotropy._verify_witness(known_answer_stack[3][known_answer_stack[5].index(
        "S2(rank 1)#1")], ramped[0].witness)[0]
    with pytest.raises(ValueError, match="one weight per shell"):
        isotropy.powder_relations(subset, reflections, weights=np.ones(n_shells - 1))
    with pytest.raises(ValueError, match="positive and finite"):
        isotropy.powder_relations(subset, reflections, weights=np.r_[0.0, np.ones(n_shells - 1)])


#: One stored witness of the known answer, S1(rank 1)#2 → S2(rank 1)#1, the
#: second draw of that direction at seed 20260906, as this module issued it
#: (Mac and Linux x86-64 agree on its d to 1e-11).  ``t`` is the draw's
#: intensity on every shell; on the ten shells S2(rank 1)#1 is dark at, where
#: the draw is round-off (≤ 3e-28), it is written as 0, since only ``live``
#: is read.  21 + 11 floats are the whole certificate.
KNOWN_WITNESS_T = (
    2.0396393395864063, 0.0, 252.06544346393682, 0.0, 62.70070903511004, 0.0,
    49.55375266228131, 0.0, 137.48616945846405, 0.0, 498.8713302469807, 0.0,
    381.00297278756, 82.28384194390448, 0.0, 190.7827456811467, 0.0,
    189.62545190032296, 0.0, 323.70047257503467, 0.0)
KNOWN_WITNESS_LIVE = (0, 2, 4, 6, 8, 10, 12, 13, 15, 17, 19)
KNOWN_WITNESS_Y = (
    168.669104663701, -83.7818311668111, -11.145777187393524, 27.298573695204375,
    47.65852630835245, 7.687155677427313, 5.790285362209989, 46.895126357899464,
    4.678876175141169, -0.5806536292744398, 6.392822745987245)


@pytest.mark.xdist_group("magnetic-known-answer")
def test_a_stored_known_answer_witness_reverifies_from_its_literals(known_answer_stack):
    """A certificate needs no generator: the stored t and y prove the draw out of S2(rank 1)#1's reach on any machine.

    Rebuilt from the literals alone against S2(rank 1)#1's stack: |y·t̂ + 1|
    ≤ 1e-9, projected ratio ≥ :data:`isotropy.FARKAS_FLOOR`, exact LDLᵀ, and
    d_lo = 1/‖y‖ = 0.0049.  It survives a change of S2(rank 1)#1's
    amplitude basis (G_s → QᵀG_sQ is a congruence).  The negative arms: −y,
    and the same y against S1(rank 1)#2's own stack, which reproduces its
    own draw.
    """
    from dataclasses import replace

    found, reflections, canonical, grams, dark, labels = known_answer_stack
    b, a = labels.index("S2(rank 1)#1"), labels.index("S1(rank 1)#2")
    y = np.array(KNOWN_WITNESS_Y)
    witness = isotropy.Witness(
        draw=2, t=KNOWN_WITNESS_T, live=KNOWN_WITNESS_LIVE, y=KNOWN_WITNESS_Y, weights=None,
        kernel_dim=0, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"), ratio=1e-10,
        rounding_bound=7.9e-15, exact=True, d=(1.0 / float(np.linalg.norm(y)), 0.00495),
        # the quoted y's own direction: strictly inside the PSD cone (ratio 1e-10), so
        # a valid interior, with the small margin that goes with the quoted point
        interior=tuple(y / float(np.linalg.norm(y))), margin=2.3e-11)
    holds, ratio, off = isotropy._verify_witness(grams[b], witness)
    assert holds and ratio >= isotropy.FARKAS_FLOOR and off <= 1e-9
    assert witness.d[0] == pytest.approx(0.00494, rel=2e-3)
    q, _ = np.linalg.qr(np.random.default_rng(5).normal(size=(grams[b].shape[1],) * 2))
    assert isotropy._verify_witness(np.einsum("ki,skl,lj->sij", q, grams[b], q), witness)[0]
    assert not isotropy._verify_witness(grams[b], replace(witness, y=tuple(-y)))[0]
    assert not isotropy._verify_witness(grams[a], witness)[0]


def test_the_quote_target_is_never_below_the_accept_floor():
    """An anchor whose ratio is under 2·FARKAS_FLOOR must not drag the quoted point under the floor (review of #772, item 2)."""
    stack = np.array([np.diag([1.0, 0.0]), np.diag([0.0, 1.0])])
    y_mn = np.array([1.0, 0.0])                     # on the PSD boundary, ratio 0
    anchor = np.array([1.0, 1.5 * isotropy.FARKAS_FLOOR])   # interior, ratio 1.5 floors
    y = isotropy._quote_inside(stack, y_mn, anchor)
    assert isotropy._spectrum_ratio(stack, y) >= isotropy.FARKAS_FLOOR
    # the positive arm: an anchor well inside still quotes at the FARKAS_QUOTE target
    y = isotropy._quote_inside(stack, y_mn, np.array([1.0, 1.0]))
    assert isotropy._spectrum_ratio(stack, y) >= isotropy.FARKAS_QUOTE


# --------------------------------------------------------------------------
# II. The isometry certificate, its propagation and the full-stack guard
#     (issue #565, part 3)
# --------------------------------------------------------------------------

@pytest.mark.xdist_group("magnetic-known-answer")
def test_the_rank_one_copies_of_each_known_answer_irrep_are_isometric(known_answer_stack):
    """Issue #565 part 3's acceptance: the two rank-1 copies of each irrep certify at residual ≤ 1e-12, and the claim holds on a draw.

    For S1 to S4 of ``P n -3 m:1`` at (0, 0, ½): an orthogonal Q with
    QᵀG^#2_sQ = G^#1_s, one-dimensional intertwiner space, both residuals
    ≤ :data:`isotropy.ISOMETRY_RESIDUAL` (measured ≤ 1.3e-14 and ≤ 1e-13),
    and the statement it proves checked by the route it replaces: a random
    amplitude x of copy #1 and Qx of copy #2 give the same intensity on
    every shell to 1e-13 of the largest.  The stored record re-verifies
    against the two stacks, and fails against −Q's transpose-free
    corruption (a Q with one row negated is still orthogonal and is not an
    intertwiner) and against another irrep's stack.
    """
    found, reflections, canonical, grams, dark, labels = known_answer_stack
    rng = np.random.default_rng(3)
    for irrep in ("S1", "S2", "S3", "S4"):
        a, b = labels.index(f"{irrep}(rank 1)#1"), labels.index(f"{irrep}(rank 1)#2")
        record = isotropy._isometry(grams[a], grams[b])
        assert record is not None, irrep
        assert record.residual <= isotropy.ISOMETRY_RESIDUAL
        assert record.orthogonality <= isotropy.ISOMETRY_RESIDUAL
        assert record.dimension == 1 and record.driver == "gesdd"
        q = np.asarray(record.q)
        assert q.shape == (18, 18)
        x = rng.normal(size=18)
        own, image = (grams[a] @ x) @ x, (grams[b] @ (q @ x)) @ (q @ x)
        assert float(np.max(np.abs(own - image))) <= 1e-13 * float(np.max(own))
        assert isotropy._verify_isometry(grams[a], grams[b], record)[0]
        from dataclasses import replace

        flipped = q.copy()
        flipped[0] *= -1.0
        corrupt = replace(record, q=tuple(tuple(row) for row in flipped))
        holds, residual, orthogonality = isotropy._verify_isometry(grams[a], grams[b], corrupt)
        assert not holds and orthogonality <= 1e-12 and residual > 1e-3
        other = labels.index("S2(rank 1)#1" if irrep != "S2" else "S1(rank 1)#1")
        assert not isotropy._verify_isometry(grams[a], grams[other], record)[0]
        # both directions of the verdict re-verify against the stacks they sit on:
        # the (b, a) record holds Qᵀ, which acts on b's amplitudes
        silent = [bool(not np.any(g)) for g in grams]
        spans = [isotropy._intensity_span(g) for g in grams]
        both = isotropy._isometry_verdicts(a, b, grams[a], grams[b], dark, spans, silent)
        assert set(both) == {(a, b), (b, a)}
        for (u, w), v in both.items():
            holds, residual, orthogonality = isotropy._verify_isometry(
                grams[u], grams[w], v.isometry)
            assert holds, (irrep, u, w)
            assert v.isometry.residual == pytest.approx(residual, abs=1e-15)
        assert np.allclose(both[(b, a)].isometry.q, np.asarray(both[(a, b)].isometry.q).T)


def test_a_singular_or_absent_intertwiner_is_no_isometry():
    """The negative arms, synthetic: a family inside a larger one, two with different spectra, equal images with no intertwiner, two of different size, a zero stack.

    A_s = diag(a_s, 0) against B_s = diag(a_s, b_s) with b_s ≠ a_s, 0: the
    intertwiner space is spanned by e₁e₁ᵀ alone, a *singular* matrix whose
    scaled copy has ‖QᵀQ − I‖ = 1 and congruence residual 1, while B's
    image (every (a_s x², b_s y²)) is strictly larger than A's, so both
    checks refuse what a containment could not be certified as.  Its
    spectra differ too, so :func:`isotropy._isometry` refuses it before
    any SVD (the operator is not built).  The quadrant (x², y²) and the
    projector pair (x², (x + y)²/2) have the *same* image and no
    intertwiner at all: no isometry proves nothing, and the pair is left
    to the draws.  The positive arm beside them: a swap of the amplitude
    axes certifies.  A size mismatch and a zero stack are not applicable.
    """
    a = np.array([np.diag([1.0, 0.0]), np.diag([2.0, 0.0])])
    b = np.array([np.diag([1.0, 3.0]), np.diag([2.0, 1.0])])
    basis, driver = isotropy._intertwiners(a, b)
    assert driver == "gesdd" and basis.shape[0] == 1
    assert np.allclose(np.abs(basis[0]), np.diag([1.0, 0.0]), atol=1e-12)
    q, orthogonality = isotropy._orthogonal_in_span(basis)
    assert orthogonality == pytest.approx(1.0) and isotropy._congruence_residual(a, b, q) > 0.5
    scaled = isotropy._trace_scaled(a, b)
    assert scaled is not None and not isotropy._spectra_agree(*scaled)
    calls = []
    real = isotropy._intertwiners

    def counting(*args):
        calls.append(1)
        return real(*args)

    import unittest.mock

    with unittest.mock.patch.object(isotropy, "_intertwiners", counting):
        assert isotropy._isometry(a, b) is None
        assert calls == []
        quadrant = np.array([np.diag([1.0, 0.0]), np.diag([0.0, 1.0])])
        projector = np.array([np.diag([1.0, 0.0]), 0.5 * np.ones((2, 2))])
        assert isotropy._spectra_agree(*isotropy._trace_scaled(quadrant, projector))
        assert isotropy._isometry(quadrant, projector) is None
        assert calls == [1]
        assert isotropy._intertwiners(quadrant, projector)[0].shape[0] == 0
        swapped = np.array([np.diag([1.0, 1.0]), np.diag([0.0, 2.0])])
        same = np.array([np.diag([1.0, 1.0]), np.diag([2.0, 0.0])])
        record = isotropy._isometry(same, swapped)
        assert record is not None and record.residual <= isotropy.ISOMETRY_RESIDUAL
    # equal spectra on every shell, A ⊊ B, and a two-dimensional intertwiner
    # space holding only singular matrices: the alternating projection's
    # polar factor is orthogonal and is not an intertwiner, so the
    # congruence residual is what refuses it
    inner = np.array([np.diag([1.0, 1.0, 0.0]), np.diag([1.0, 0.0, 0.0])])
    outer = np.array([np.diag([1.0, 1.0, 0.0]), np.diag([0.0, 0.0, 1.0])])
    assert isotropy._spectra_agree(*isotropy._trace_scaled(inner, outer))
    basis, _ = isotropy._intertwiners(inner, outer)
    assert basis.shape[0] == 2
    assert all(np.linalg.matrix_rank(m, tol=1e-9) == 1 for m in basis)
    q, orthogonality = isotropy._orthogonal_in_span(basis)
    assert orthogonality <= 1e-12 and isotropy._congruence_residual(inner, outer, q) > 0.5
    assert isotropy._isometry(inner, outer) is None
    assert isotropy._isometry(a, np.zeros((2, 3, 3))) is None
    assert isotropy._isometry(a, np.zeros_like(a)) is None
    assert isotropy._isometry(np.zeros_like(a), np.zeros_like(a)) is None


def test_an_isometry_is_found_in_a_multi_dimensional_intertwiner_space_and_up_to_scale():
    """The positive arm, synthetic: A_s = diag(a_s, a_s, b_s) against B_s = 3·Q₀ᵀA_sQ₀ for a random orthogonal Q₀.

    The commutant of A is the 2 × 2 block times the last diagonal entry,
    five-dimensional, so the intertwiner space of (A, B) has dimension 5
    and the alternating projection must land on an orthogonal element;
    the factor 3 is removed by the trace scaling, since a scale is
    refinable.  The certificate re-verifies, and B with one shell scaled
    on its own (no longer one overall scale) gets none.
    """
    rng = np.random.default_rng(11)
    q0, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    a = np.array([np.diag([1.0, 1.0, 0.5]), np.diag([0.2, 0.2, 2.0]), np.diag([1.5, 1.5, 0.1])])
    b = 3.0 * np.einsum("ki,skl,lj->sij", q0, a, q0)
    record = isotropy._isometry(a, b)
    assert record is not None
    assert record.dimension == 5
    assert record.residual <= isotropy.ISOMETRY_RESIDUAL
    assert record.orthogonality <= isotropy.ISOMETRY_RESIDUAL
    q = np.asarray(record.q)
    x = rng.normal(size=3)
    assert np.allclose((a @ x) @ x, ((b @ (q @ x)) @ (q @ x)) / 3.0, rtol=1e-12, atol=0.0)
    assert isotropy._verify_isometry(a, b, record)[0]
    lopsided = b.copy()
    lopsided[1] *= 1.01
    assert isotropy._isometry(a, lopsided) is None


def test_the_intertwiner_svd_falls_back_to_gesvd_when_gesdd_does_not_converge(monkeypatch):
    """LAPACK's gesdd failed on two ``F m -3 m`` Γ families; the same SVD by gesvd answers, and the driver is recorded."""
    a = np.array([np.diag([1.0, 2.0]), np.diag([3.0, 1.0])])
    b = a[:, ::-1, ::-1].copy()                     # the swap: an isometry
    operator_shape = (a.shape[0] * 4, 4)
    real = np.linalg.svd
    calls = []

    def flaky(matrix, *args, **kwargs):
        if matrix.shape == operator_shape:
            calls.append(matrix.shape)
            raise np.linalg.LinAlgError("SVD did not converge")
        return real(matrix, *args, **kwargs)

    monkeypatch.setattr(np.linalg, "svd", flaky)
    record = isotropy._isometry(a, b)
    assert record is not None and record.driver == "gesvd" and calls == [operator_shape]
    assert record.residual <= isotropy.ISOMETRY_RESIDUAL
    monkeypatch.setattr(np.linalg, "svd", real)
    assert isotropy._isometry(a, b).driver == "gesdd"


def _coupled_stack(eps):
    """The synthetic stack with a third amplitude that only shell 0 sees, through (1, 0, ε)(1, 0, ε)ᵀ: a kernel at residual about ε."""
    padded = np.zeros((3, 3, 3))
    padded[:, :2, :2] = SYNTHETIC_STACK
    v = np.array([1.0, 0.0, eps])
    padded[0] = np.outer(v, v)
    return padded


def test_the_full_stack_guard_refuses_a_kernel_the_quoted_margin_cannot_cover():
    """The promise made on #772: the kernel guard is tied to the quoted margin, and the certificate states what the full stack proves.

    A kernel direction coupled at r_K ≈ 5e-10 passes the 1e-9 pre-screen
    but gives ρ_max ≈ 0.03 < :data:`isotropy.KERNEL_AMPLITUDE_RATIO`: the
    dual is solved (its optimum is returned) and the certificate refused.
    At r_K ≈ 1e-13 the same draw certifies with ρ_max ≈ 30 recorded on the
    witness; that number is rebuilt from the bound's own parts (r_K, Λ, Y
    and the quoted margin), so a wrong formula shows, and the inequality
    the record states is checked on random amplitudes with kernel share
    up to ρ_max: y·I(b) > 0 on all of them.
    Without a kernel ρ_max is infinite.  A stored witness is re-verified
    with the same guard: the accepted one holds against its own stack and
    fails against the 5e-10 stack, whose kernel its margin cannot cover.
    Under :data:`isotropy.INTENSITY_RTOL` alone (part 2's guard) both
    stacks would certify.
    """
    loose = _coupled_stack(5e-10)
    _, kernel, residual = isotropy._live_projection(loose)
    assert kernel == 1 and 1e-10 < residual < isotropy.INTENSITY_RTOL
    dual, parts = isotropy._farkas_certificate(loose, SYNTHETIC_OUT)
    assert dual is not None and dual >= isotropy.FARKAS_FLOOR and parts is None

    tight = _coupled_stack(1e-13)
    _, kernel, residual = isotropy._live_projection(tight)
    assert kernel == 1 and 0.0 < residual < 1e-12
    dual, parts = isotropy._farkas_certificate(tight, SYNTHETIC_OUT)
    assert parts is not None and parts["kernel_dim"] == 1
    rho = parts["kernel_amplitude_ratio"]
    assert isotropy.KERNEL_AMPLITUDE_RATIO <= rho < 1e3
    assert rho == pytest.approx(isotropy._kernel_amplitude_ratio(tight, parts["y"]))
    assert isotropy._kernel_amplitude_ratio(SYNTHETIC_STACK, np.array([1.0, 1.0, -0.5])) == np.inf
    # the recorded number is the documented bound, rebuilt here from its parts
    g = tight / np.max(np.abs(tight))
    k, p, r_k = isotropy._common_kernel(g)
    m = np.einsum("s,sij->ij", parts["y"], g)
    spectrum = np.linalg.eigvalsh(p.T @ m @ p)
    lam = float(np.max(np.abs(spectrum)))
    big_y = float(sum(abs(y_s) * np.linalg.norm(g_s, 2) for y_s, g_s in zip(parts["y"], g)))
    x = (spectrum[0] / lam) * lam / (r_k * big_y)
    assert rho == pytest.approx(-1.0 + np.sqrt(1.0 + x), rel=1e-12)
    assert r_k * big_y * (2 * rho + rho ** 2) == pytest.approx(spectrum[0], rel=1e-9)
    # the inequality the record states, on the full (unprojected) float stack
    rng = np.random.default_rng(7)
    for _ in range(200):
        u = rng.normal(size=p.shape[1])
        v = rng.normal(size=k.shape[1])
        v *= rho * np.linalg.norm(u) / np.linalg.norm(v) * rng.uniform(0.0, 1.0)
        b = p @ u + k @ v
        assert float(b @ m @ b) > 0.0

    witness = isotropy.Witness(
        draw=1, t=tuple(SYNTHETIC_OUT), live=(0, 1, 2), y=tuple(parts["y"]), weights=None,
        kernel_dim=1, kernel_residual=parts["kernel_residual"], kernel_amplitude_ratio=rho,
        ratio=parts["ratio"], rounding_bound=parts["rounding_bound"], exact=True,
        d=(1.0 / float(np.linalg.norm(parts["y"])), 1.0),
        interior=tuple(parts["interior"]), margin=parts["margin"])
    assert isotropy._verify_witness(tight, witness)[0]
    holds, ratio, off = isotropy._verify_witness(loose, witness)
    assert not holds and ratio >= isotropy.FARKAS_FLOOR and off <= 1e-9


def test_propagation_carries_only_proofs_and_refuses_two_that_disagree():
    """:func:`isotropy._propagate` on hand-built verdicts: copies inherit a proof, a sample carries nothing, a proved contradiction raises.

    Five candidates, 0 ≅ 1 and 3 ≅ 4 (2 alone).  A ``farkas`` 0 → 3
    reaches (0, 4), (1, 3) and (1, 4): an undecided direction, a sampled
    one and an unresolved one are all replaced, with ``via`` (0, 3) and the
    source's witness-less ``d``; a direction already proved the same way
    is left as it was; one proved the *other* way raises.  A sampled
    source and a propagated source carry nothing.
    """
    copies = [0, 0, 2, 3, 3]
    source = isotropy.PairVerdict(0, 3, "proved-not", "farkas", 4, 0, d=(0.01, 0.1), dual=1e-6)
    verdicts = {(1, 3): isotropy.PairVerdict(1, 3, "sampled-contained", None, 12, 0),
                (1, 4): isotropy.PairVerdict(1, 4, "unresolved", None, reason="joined"),
                (3, 0): isotropy.PairVerdict(3, 0, "sampled-contained", None, 2, 0),
                (0, 2): isotropy.PairVerdict(0, 2, "sampled-contained", None, 3, 0)}
    isotropy._propagate(source, verdicts, list(copies), 5)
    for key, spent in {(0, 4): 0, (1, 3): 12, (1, 4): 0}.items():   # a drawn direction keeps its 12 draws
        v = verdicts[key]
        assert (v.status, v.certificate, v.draws, v.via, v.d, v.dual) == \
            ("proved-not", "propagated", spent, (0, 3), (0.01, 0.1), 1e-6), key
    assert verdicts[(3, 0)].status == "sampled-contained"        # the other direction is not the source's
    assert verdicts[(0, 2)].status == "sampled-contained"        # 2 is nobody's copy
    assert (0, 3) not in verdicts                                # the source itself is the caller's
    kept = isotropy.PairVerdict(1, 3, "proved-not", "absence")
    verdicts[(1, 3)] = kept
    isotropy._propagate(source, verdicts, list(copies), 5)
    assert verdicts[(1, 3)] is kept
    verdicts[(1, 4)] = isotropy.PairVerdict(1, 4, "proved-contained", "absence")
    with pytest.raises(RuntimeError, match="two certificates disagree"):
        isotropy._propagate(source, verdicts, list(copies), 5)
    fresh = {}
    isotropy._propagate(isotropy.PairVerdict(0, 3, "sampled-not", None, 5, 1), fresh,
                        list(copies), 5)
    isotropy._propagate(isotropy.PairVerdict(0, 3, "proved-not", "propagated", via=(1, 4)),
                        fresh, list(copies), 5)
    assert fresh == {}


# --------------------------------------------------------------------------
# III. The span-containment certificate, the containment transfers and the
#      sign-free fit transfer (issue #565, part 4)
# --------------------------------------------------------------------------

@pytest.mark.xdist_group("magnetic-known-answer")
def test_a_rank_one_direction_is_proved_inside_its_plane(known_answer_stack):
    """S1(rank 1)#1 ⊆ S1(a,b) by an injection congruence G^A_s = c·EᵀG^B_sE, c = ½; the plane is not inside the line, and S1 is not inside S2.

    The record is proved by its congruence residual on the Gram stacks
    (≤ 1e-13 here against :data:`isotropy.ISOMETRY_RESIDUAL` = 1e-12), re-
    verified from E alone, and checked on random amplitudes:
    I_A(x) = c·I_B(Ex) on every shell.  Here the patterns are in span
    (pattern residual at rounding, domain 0).  Negative arms: the reverse
    direction, a cross-irrep pair (S1 against both S2 families) and an E
    scaled by 1 %.
    """
    found, reflections, canonical, grams, dark, labels = known_answer_stack
    little = irreps.little_group(found.space_group, found.k)
    a, b = labels.index("S1(rank 1)#1"), labels.index("S1(a,b)")
    patterns = {i: isotropy._domain_patterns(canonical[i], little) for i in (a, b)}
    record = isotropy._containment(canonical[a], grams[a], grams[b], patterns[b])
    assert record is not None
    assert record.residual <= 1e-13 and record.pattern_residual <= 1e-12 and record.domain == 0
    assert record.scale == pytest.approx(0.5, rel=1e-9)
    e = np.array(record.e)
    assert e.shape == (canonical[b].free_amplitudes, canonical[a].free_amplitudes)
    rng = np.random.default_rng(11)
    for _ in range(5):
        x = rng.normal(size=canonical[a].free_amplitudes)
        left = (grams[a] @ x) @ x
        right = record.scale * ((grams[b] @ (e @ x)) @ (e @ x))
        assert np.allclose(left, right, rtol=0.0, atol=1e-12 * np.max(np.abs(left)))
    holds, residual = isotropy._verify_containment(grams[a], grams[b], record)
    assert holds and residual == pytest.approx(record.residual)
    from dataclasses import replace

    wrong = replace(record, e=tuple(tuple(1.01 * v for v in row) for row in record.e))
    assert not isotropy._verify_containment(grams[a], grams[b], wrong)[0]
    assert isotropy._containment(canonical[b], grams[b], grams[a], patterns[a]) is None
    for other in ("S2(rank 1)#1", "S2(a,b)"):
        c = labels.index(other)
        assert isotropy._containment(canonical[a], grams[a], grams[c],
                                     isotropy._domain_patterns(canonical[c], little)) is None
    assert hash(isotropy.PairVerdict(a, b, "proved-contained", "span", containment=record))


@pytest.mark.xdist_group("magnetic-known-answer")
def test_the_span_certificate_decides_one_direction_and_the_draws_the_other(known_answer_stack):
    """S1(rank 1)#1 → S1(a,b) is proved contained and not drawn; S1(a,b) → S1(rank 1)#1 is drawn as before and sampled.

    The pair is equivalent at this seed (the plane's three draws are
    reproduced by the line), joined by one proved and one sampled
    direction, and printed as ``n = 0 (span), 3``.  The same with the
    candidates the other way round, so the certificate reads the pair and
    not the order.
    """
    from dataclasses import replace

    found, reflections = known_answer_stack[0], known_answer_stack[1]
    pick = {c.label: c for c in found}
    for names in (("S1(rank 1)#1", "S1(a,b)"), ("S1(a,b)", "S1(rank 1)#1")):
        subset = replace(found, candidates=tuple(pick[name] for name in names))
        line, plane = names.index("S1(rank 1)#1"), names.index("S1(a,b)")
        classes, relations = isotropy._classify(subset, reflections, draws=None, seed=20260906,
                                                rtol=1e-4, restarts=4)
        verdicts = {(v.a, v.b): v for v in relations}
        there, back = verdicts[(line, plane)], verdicts[(plane, line)]
        assert (there.status, there.certificate, there.draws) == ("proved-contained", "span", 0)
        assert there.containment is not None and there.containment.residual <= 1e-13
        assert (back.status, back.certificate, back.draws) == \
            ("sampled-contained", None, isotropy.WITHIN_IRREP_DRAWS)
        assert classes == ((0, 1),)
        text = str(replace(subset, classes=classes, relations=relations))
        assert "proved contained (span)" in text
        assert f"  S1(rank 1)#1 ⊆ S1(a,b)  residual {there.containment.residual:.1e}" in text
        assert f"n = {'0 (span), 3' if line == 0 else '3, 0 (span)'}" in text
    assert isotropy.powder_equivalent(pick["S1(rank 1)#1"], pick["S1(a,b)"], reflections,
                                      restarts=4)


#: ``F -4 3 m`` at the general site (0.11, 0.13, 0.17), k = 0: 17 families,
#: the set of issue #565's control, where at seed 2 one draw of S4 refutes
#: the sampled S4 ∪ S5 join.
F43M_GAMMA = ("F -4 3 m", (0.11, 0.13, 0.17), GAMMA)


@pytest.fixture(scope="module")
def f43m_stack():
    """``F43M_GAMMA``'s candidates, canonical bases, Gram stacks and dark shells, built once (about 8 s)."""
    return _stack(F43M_GAMMA)


#: The stored ``F -4 3 m`` Γ seed-2 witness (issue #565, part 4's acceptance):
#: draw 106 of S4(rank 1)#2 against S5(rank 2)#1, as the 2026-09-30 run
#: certified it on two machines (projected ratio +2.3e-6, d = 0.0052,
#: exact-PSD).  ``t`` is the draw's intensity on the 10 shells; S5(rank 2)#1
#: is dark on six of them, where the draw is round-off (≤ 1.2e-28), and
#: live on the four of ``F43M_WITNESS_LIVE``.  ``y`` is the minimum-norm
#: certificate on those four, and ``interior`` the unit direction of the
#: dual's maximiser.  10 + 4 + 4 floats are the whole certificate.
F43M_WITNESS_T = (
    1.638282726408967e-30, 2.8349583371292487e-30, 20.410358836281144, 29.833248177617417,
    4.50951298428427e-29, 7.401540777828149e-29, 15.147160346230379, 1.1759478936183933e-28,
    3.693491135362942e-29, 33.79497696858829)
F43M_WITNESS_LIVE = (2, 3, 6, 9)
F43M_WITNESS_Y = (17.569507673668543, -153.36716017587415, 50.04865784868707,
                  100.81364403558946)
F43M_WITNESS_INTERIOR = (0.08935432309765487, -0.7990132994368212, 0.2582331904393587,
                         0.5356390310856317)


def _f43m_witness():
    y = np.array(F43M_WITNESS_Y)
    return isotropy.Witness(
        draw=106, t=F43M_WITNESS_T, live=F43M_WITNESS_LIVE, y=F43M_WITNESS_Y, weights=None,
        kernel_dim=0, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"), ratio=6.1e-10,
        rounding_bound=6.0e-15, exact=True, d=(1.0 / float(np.linalg.norm(y)), 0.00524),
        interior=F43M_WITNESS_INTERIOR, margin=8.42e-7)


@pytest.mark.xdist_group("magnetic-f43m")
def test_the_stored_f43m_witness_transfers_to_the_family_that_reproduces_it(f43m_stack):
    """Issue #565's part-4 acceptance, the fit transfer: S4(rank 1)#1 reproduces the stored draw and the sign-free bound fires; nothing of S5's fires.

    Rebuilt from the literals against the stack this module builds, the
    witness re-verifies on S5(rank 2)#1 (and not on S4(rank 1)#2's own
    stack, nor with the interior negated), and its margin is μ = 8.4e-7
    on this stack.  **Positive arm:** S4(rank 1)#1 is fitted to the draw,
    reaches it (δ ≤ 1e-10), and :func:`isotropy._fit_transfer` fires with
    ρ/μ ≤ 1e-4, so S4(rank 1)#1 ⊄ S5(rank 2)#1; the record re-verifies
    from its stored amplitudes.  **The sign is not what decides:** |cos|
    is at rounding (≤ 1e-9, and +9e-16 on one machine), so the bound fires
    with cos replaced by +|cos| just the same.  **The kernel projection:**
    S4(rank 1)#1 has a one-dimensional common kernel; a kernel component
    of 1e3·‖x‖ added to the fitted amplitudes leaves I_c unchanged and the
    stored x the projected one, while the unprojected κ_c (3e9) would take
    ρ past μ (ρ/μ 18) and nothing could fire.  **Negative arms:** five
    draws of S5(rank 2)#1 itself, of each of its proved sub-families
    S5(rank 1)#1 (in the span of a conjugate of S5(rank 2)#1: domain > 0)
    and S5(rank 1)#3 (in span as written, domain 0), of its isometric copy
    S5(rank 2)#2 and of S5(a,b,c), and three points of the PSD relaxation,
    all sit at cos ≥ 1e4 μ and none fires.  The third kind of containment,
    a least-squares E that reproduces the Gram stack and not the patterns
    (pattern residual 0.5), is S4(rank 1)#3 ⊆ S4(rank 2)#2.
    """
    found, reflections, canonical, grams, dark, labels = f43m_stack
    little = irreps.little_group(found.space_group, found.k)
    a, b, c = (labels.index(name) for name in ("S4(rank 1)#2", "S5(rank 2)#1", "S4(rank 1)#1"))
    witness = _f43m_witness()
    t = np.asarray(witness.t)
    assert tuple(np.flatnonzero(isotropy._fit_rows(t, grams[b]) & ~dark[b])) == witness.live
    holds, ratio, off = isotropy._verify_witness(grams[b], witness)
    assert holds and ratio >= isotropy.FARKAS_FLOOR and off <= 1e-9
    assert not isotropy._verify_witness(grams[a], witness)[0]
    from dataclasses import replace

    negated = replace(witness, interior=tuple(-v for v in witness.interior))
    assert not isotropy._verify_witness(grams[b], negated)[0]
    live = np.array(witness.live)
    g, t_hat = isotropy._certificate_stack(grams[b][live], t[live], None)
    projected = isotropy._live_projection(g)[0]
    lam, gamma, mu = isotropy._cone_margin(projected, np.array(witness.interior))
    assert mu == pytest.approx(8.42e-7, rel=1e-2) and lam > 0.0

    x = isotropy._transfer_fit(t, grams[c], np.random.default_rng([20260906, a, b, c]),
                               restarts=8, rtol=1e-4)
    assert x is not None
    fires, record = isotropy._fit_transfer(witness, grams[b], dark[b], grams[c], x)
    assert fires and record is not None
    assert record.fit <= 1e-10 and record.mu == pytest.approx(mu)
    assert record.rho / record.mu <= 1e-4 and not record.float_stack
    assert (record.n_b, record.n_c, record.shells) == (18, 9, 4)
    assert abs(record.cos) <= 1e-9                       # rounding, either sign
    assert abs(record.cos) < record.mu - record.rho      # fires with the sign flipped
    assert isotropy._verify_transfer(witness, grams[b], dark[b], grams[c], record)
    assert hash(isotropy.PairVerdict(c, b, "proved-not", "transfer", transfer=record,
                                     witness=witness, via=(a, b)))

    gc = grams[c] / np.max(np.abs(grams[c]))
    kernel, _, _ = isotropy._common_kernel(gc)
    assert kernel.shape[1] == 1
    shifted = x + kernel @ (np.ones(1) * 1e3 * np.linalg.norm(x))
    fires_s, record_s = isotropy._fit_transfer(witness, grams[b], dark[b], grams[c], shifted)
    assert fires_s and np.allclose(record_s.x, record.x, atol=1e-9)
    assert record_s.kappa == pytest.approx(record.kappa, rel=1e-6)
    eps = np.finfo(float).eps
    i_live = ((grams[c] @ shifted) @ shifted)[live]
    gamma_c = np.sqrt(np.sum(np.linalg.norm(grams[c][live], 2, axis=(1, 2)) ** 2))
    kappa_raw = gamma_c * float(shifted @ shifted) / np.linalg.norm(i_live)
    rho_raw = (4 * record.shells * eps + record.shells * np.sqrt(record.n_b) * eps
               + 2 * (record.n_c + 1) * eps * kappa_raw)
    assert kappa_raw > 1e8 and rho_raw > record.mu

    rng = np.random.default_rng(3)
    for name in ("S5(rank 2)#1", "S5(rank 1)#1", "S5(rank 1)#3", "S5(rank 2)#2", "S5(a,b,c)"):
        f = labels.index(name)
        for _ in range(5):
            draw = isotropy._normalised_draw(canonical[f], reflections.lattice, rng)
            fired, probe = isotropy._fit_transfer(witness, grams[b], dark[b], grams[f], draw)
            assert not fired and probe is not None and probe.cos >= 1e4 * probe.mu, name
    patterns_b = isotropy._domain_patterns(canonical[b], little)
    inside = {name: isotropy._containment(canonical[labels.index(name)],
                                          grams[labels.index(name)], grams[b], patterns_b)
              for name in ("S5(rank 1)#1", "S5(rank 1)#3")}
    assert all(r is not None and r.residual <= 1e-13 for r in inside.values())
    assert inside["S5(rank 1)#3"].domain == 0 and inside["S5(rank 1)#3"].pattern_residual <= 1e-12
    assert inside["S5(rank 1)#1"].domain > 0 and inside["S5(rank 1)#1"].pattern_residual <= 1e-12
    s4_3, s4_r2 = labels.index("S4(rank 1)#3"), labels.index("S4(rank 2)#2")
    stack_only = isotropy._containment(canonical[s4_3], grams[s4_3], grams[s4_r2],
                                       isotropy._domain_patterns(canonical[s4_r2], little))
    assert stack_only is not None and stack_only.residual <= 1e-13
    assert stack_only.pattern_residual > 0.1 and stack_only.domain > 0
    assert isotropy._verify_containment(grams[s4_3], grams[s4_r2], stack_only)[0]
    n = grams[b].shape[1]
    for _ in range(3):
        z = rng.normal(size=(n, n))
        relaxed = np.einsum("sij,ij->s", grams[b], z @ z.T)[live]
        assert float(np.array(witness.interior) @ relaxed) / np.linalg.norm(relaxed) >= 1e4 * mu


#: The eight ``F -4 3 m`` Γ families the pipeline arms below run on: the
#: three isometric S4 rank-1 copies, the rank-2 and (a,b,c) directions that
#: contain them, and S5(rank 1)#3 ⊆ S5(rank 2)#1 ≅ S5(rank 2)#2.
F43M_ARM = ["S4(rank 1)#1", "S4(rank 1)#2", "S4(rank 1)#3", "S4(rank 2)#2", "S4(a,b,c)",
            "S5(rank 1)#3", "S5(rank 2)#1", "S5(rank 2)#2"]


def _f43m_arm(f43m_stack, monkeypatch):
    """The eight-family subset with every draw stubbed reproduced except the first S4(rank 1)#1 draw against S5(rank 2)#1, which is the stored witness."""
    from dataclasses import replace

    found, reflections, canonical, grams, dark, labels = f43m_stack
    subset = replace(found, candidates=tuple(found[labels.index(name)] for name in F43M_ARM))
    target = grams[labels.index("S5(rank 2)#1")]
    witness = _f43m_witness()
    state = {"armed": False, "injected": 0}
    real_draw = isotropy._normalised_draw

    def arming(candidate, lattice, rng):
        state["armed"] = candidate.label == "S4(rank 1)#1"
        return real_draw(candidate, lattice, rng)

    def inject(t, grams_b, *args, **kwargs):
        if state["armed"] and np.array_equal(grams_b, target):
            state["armed"] = False
            state["injected"] += 1
            return False, True, witness, 2.3e-6
        return True, False, None, None

    monkeypatch.setattr(isotropy, "_normalised_draw", arming)
    monkeypatch.setattr(isotropy, "_certify_draw", inject)
    return subset, reflections, witness, state


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-f43m")
def test_the_containment_transfers_carry_the_f43m_witness_to_every_s4_family(f43m_stack,
                                                                             monkeypatch):
    """Issue #565's part-4 acceptance, the containment rules: one stored witness separates every S4 family from S5(rank 2)#1, its copy and its sub-family.

    Every draw is stubbed reproduced except the one that is the stored
    witness (S4(rank 1)#1 → S5(rank 2)#1, ``farkas``, draw 1), so the
    eight families are one sampled class; the proofs then run through it.
    Isometry carries the witness to the two other rank-1 copies and to
    S5(rank 2)#2 (``propagated``).  The first rule, A ⊆ A′: S4(rank 2)#2
    and S4(a,b,c) contain S4(rank 1)#1 (``span``), so S4(rank 2)#2 ⊄
    S5(rank 2)#1 and S4(a,b,c) ⊄ S5(rank 2)#1 (``containment``, the same
    witness and bracket, re-verified on S5(rank 2)#1's stack; the drawn
    direction keeps its 12 draws).  The second rule, C ⊆ B:
    S5(rank 1)#3 ⊆ S5(rank 2)#1, so S4(rank 1)#1 ⊄ S5(rank 1)#3 with
    d ∈ [d_lo, 1], and from there the copies and the containing families
    again.  Nineteen of the 28 pairs are proved from one draw; the
    reverse directions that were drawn (the containing S4 families and
    S5(rank 1)#3 back to S4(rank 1)#1, the two S5(rank 2) copies back to
    S4(rank 2)#2) stay sampled, the class is one and marked S, and no fit
    transfer is made.
    """
    from dataclasses import replace

    subset, reflections, witness, state = _f43m_arm(f43m_stack, monkeypatch)
    names = F43M_ARM
    classes, relations = isotropy._classify(subset, reflections, draws=None, seed=20260906,
                                            rtol=1e-4, restarts=4)
    assert state["injected"] == 1 and classes == ((0, 1, 2, 3, 4, 5, 6, 7),)
    v = {(names[r.a], names[r.b]): r for r in relations}
    found = v[("S4(rank 1)#1", "S5(rank 2)#1")]
    assert (found.status, found.certificate, found.draws) == ("proved-not", "farkas", 1)
    assert found.witness is witness
    by = {}
    for r in relations:
        by.setdefault(r.certificate, []).append((names[r.a], names[r.b]))
    assert sorted(by["containment"]) == [
        ("S4(a,b,c)", "S5(rank 1)#3"), ("S4(a,b,c)", "S5(rank 2)#1"),
        ("S4(rank 1)#1", "S5(rank 1)#3"),
        ("S4(rank 2)#2", "S5(rank 1)#3"), ("S4(rank 2)#2", "S5(rank 2)#1")]
    assert "transfer" not in by and len(by["propagated"]) == 9 and len(by["span"]) == 9
    carried = v[("S4(rank 2)#2", "S5(rank 2)#1")]
    assert (carried.via, carried.draws, carried.d) == ((0, 6), isotropy.CROSS_IRREP_DRAWS, found.d)
    assert carried.witness is witness
    grams = f43m_stack[3]
    labels = f43m_stack[5]
    for key in (("S4(rank 2)#2", "S5(rank 2)#1"), ("S4(a,b,c)", "S5(rank 2)#1")):
        assert isotropy._verify_witness(grams[labels.index(key[1])], v[key].witness)[0]
    # a containment verdict's witness verifies against the b of its ``via`` pair, the stack it
    # was issued on, rule 2's carried witness included (its own b is the smaller family)
    for r in relations:
        if r.certificate == "containment":
            assert isotropy._verify_witness(grams[labels.index(names[r.via[1]])], r.witness)[0], r
    reverse = v[("S4(rank 1)#1", "S5(rank 1)#3")]
    assert (reverse.via, reverse.d) == ((0, 6), (found.d[0], 1.0))
    assert all(r.status == "proved-not" for r in relations
               if names[r.a].startswith("S4") and names[r.b].startswith("S5"))
    sampled = sorted((names[r.a], names[r.b]) for r in relations if r.status.startswith("sampled"))
    assert sampled == [("S4(a,b,c)", "S4(rank 1)#1"), ("S4(rank 2)#2", "S4(rank 1)#1"),
                       ("S5(rank 1)#3", "S4(rank 1)#1"), ("S5(rank 2)#1", "S4(rank 2)#2"),
                       ("S5(rank 2)#2", "S4(rank 2)#2")]
    result = replace(subset, classes=classes, relations=relations)
    text = str(result)
    assert _table_marks(result) == ["S"] * 8
    assert ("proved 19 (absence 0, subspace 0, isometry 4, farkas 1, propagated 9, span 0, "
            "containment 5, transfer 0)") in text
    assert "proved separations carried by containment (containment):" in text
    assert (f"  S4(rank 2)#2 ⊄ S5(rank 2)#1  via S4(rank 1)#1 ⊄ S5(rank 2)#1"
            f"  d ∈ [{found.d[0]:.2g}, {found.d[1]:.2g}]") in text
    assert f"  S4(rank 1)#1 ⊄ S5(rank 1)#3  via S4(rank 1)#1 ⊄ S5(rank 2)#1  d ∈ [{found.d[0]:.2g}, 1]" in text
    assert "classes holding a proved separation (part 5 of issue #565 splits them): 0" in text


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-f43m")
def test_the_fit_transfer_reaches_the_families_the_containments_would_have(f43m_stack,
                                                                            monkeypatch):
    """With the span certificate switched off, the fit transfer alone carries the witness to S4(rank 2)#2 and S4(a,b,c).

    Same arm, :func:`isotropy._containment` returning None: the draws
    said both families reproduce S4(rank 1)#1, so each is fitted to the
    witness draw, reaches it (δ ≤ 1e-9) and fires the bound (|cos| ≤ 1e-9
    against μ − ρ = 8.4e-7), giving ``transfer`` verdicts ``via`` the
    witness pair with the bracket moved by δ, carried on to S5(rank 2)#2
    by isometry.  S5(rank 1)#3 also reproduced S4(rank 1)#1's draws, is
    fitted to the witness, does not reach it, and its direction to
    S5(rank 2)#1 stays what the loop left it (joined, not drawn): a fit
    that fails decides nothing.  No ``containment`` verdict exists.
    """
    from dataclasses import replace

    monkeypatch.setattr(isotropy, "_containment", lambda *args, **kwargs: None)
    subset, reflections, witness, state = _f43m_arm(f43m_stack, monkeypatch)
    names = F43M_ARM
    classes, relations = isotropy._classify(subset, reflections, draws=None, seed=20260906,
                                            rtol=1e-4, restarts=4)
    assert state["injected"] == 1
    v = {(names[r.a], names[r.b]): r for r in relations}
    found = v[("S4(rank 1)#1", "S5(rank 2)#1")]
    assert found.certificate == "farkas"
    transfers = {key: r for key, r in v.items() if r.certificate == "transfer"}
    assert sorted(transfers) == [("S4(a,b,c)", "S5(rank 2)#1"), ("S4(rank 2)#2", "S5(rank 2)#1")]
    grams, dark, labels = f43m_stack[3], f43m_stack[4], f43m_stack[5]
    b = labels.index("S5(rank 2)#1")
    for (c_name, _), r in transfers.items():
        record = r.transfer
        assert r.via == (0, 6) and r.witness is witness and r.status == "proved-not"
        assert abs(record.cos) <= 1e-9 and record.fit <= 1e-9
        assert record.mu == pytest.approx(8.42e-7, rel=1e-2) and record.rho / record.mu <= 1e-3
        assert abs(record.cos) < record.mu - record.rho
        assert isotropy._verify_transfer(witness, grams[b], dark[b], grams[labels.index(c_name)],
                                         record)
        assert found.d[0] - record.fit <= r.d[0] <= found.d[1] + record.fit >= r.d[1]
    assert v[("S4(rank 2)#2", "S5(rank 2)#1")].draws == isotropy.CROSS_IRREP_DRAWS
    for c_name in ("S4(a,b,c)", "S4(rank 2)#2"):
        copy = v[(c_name, "S5(rank 2)#2")]
        assert (copy.certificate, copy.via) == ("propagated", (names.index(c_name), 6))
    assert v[("S5(rank 1)#3", "S5(rank 2)#1")].status == "unresolved"
    assert v[("S4(rank 1)#1", "S5(rank 1)#3")].status == "sampled-contained"
    assert not [r for r in relations if r.certificate in ("span", "containment")]
    text = str(replace(subset, classes=classes, relations=relations))
    assert "proved separations by fit transfer (transfer), cos(ŷ, I_c) < μ − ρ:" in text
    assert "  S4(rank 2)#2 ⊄ S5(rank 2)#1  via S4(rank 1)#1 ⊄ S5(rank 2)#1  cos " in text


def test_transfers_read_only_proved_containments_and_refuse_a_contradiction():
    """:func:`isotropy._transfers` on hand-built verdicts: the two rules, what each carries, what is left alone, and the raise.

    Five candidates on copies of the synthetic stack, no isometry.  A
    ``farkas`` 0 → 3 with the synthetic witness; 0 ⊆ 1 and 4 ⊆ 3 proved
    (``span``); 0 ⊆ 2 *sampled*.  Rule 1 gives 1 ⊄ 3 (``containment``,
    ``via`` (0, 3), the witness, the bracket and the 12 draws it had);
    rule 2 gives 0 ⊄ 4 with the bracket (d_lo, 1), and the carried proofs
    seed the rules again (1 ⊄ 4, from 0 ⊄ 4 and 0 ⊆ 1); the sampled
    containment carries nothing, so 2 → 3 is untouched.  A ``transfer``
    source carries its record along rule 1.  Then with 1 ⊆ 3 also
    "proved", the rules would prove 1 ⊄ 3 against it, and raise.
    """
    _, parts = isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_OUT)
    witness = isotropy.Witness(
        draw=1, t=tuple(SYNTHETIC_OUT), live=(0, 1, 2), y=tuple(parts["y"]), weights=None,
        kernel_dim=0, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"),
        ratio=parts["ratio"], rounding_bound=parts["rounding_bound"], exact=True,
        d=(0.01, 0.1), interior=tuple(parts["interior"]), margin=parts["margin"])
    n = 5
    grams = [SYNTHETIC_STACK] * n
    dark = [np.zeros(3, dtype=bool)] * n
    silent = [False, False, True, False, False]

    def fresh():
        verdicts = {(i, j): isotropy.PairVerdict(i, j, "unresolved", None, reason="joined")
                    for i in range(n) for j in range(n) if i != j}
        verdicts[(0, 3)] = isotropy.PairVerdict(0, 3, "proved-not", "farkas", 4, 0, d=(0.01, 0.1),
                                                witness=witness, dual=1e-6)
        verdicts[(0, 1)] = isotropy.PairVerdict(0, 1, "proved-contained", "span")
        verdicts[(4, 3)] = isotropy.PairVerdict(4, 3, "proved-contained", "span")
        verdicts[(0, 2)] = isotropy.PairVerdict(0, 2, "sampled-contained", None, 12, 0)
        verdicts[(1, 3)] = isotropy.PairVerdict(1, 3, "sampled-contained", None, 12, 0)
        return verdicts

    verdicts = fresh()
    isotropy._transfers(verdicts, list(range(n)), grams, dark, silent, n=n, seed=1, rtol=1e-4,
                        restarts=2)
    carried = verdicts[(1, 3)]
    assert (carried.status, carried.certificate, carried.via, carried.draws, carried.d) == \
        ("proved-not", "containment", (0, 3), 12, (0.01, 0.1))
    assert carried.witness is witness and carried.dual == 1e-6
    reverse = verdicts[(0, 4)]
    assert (reverse.status, reverse.certificate, reverse.via, reverse.draws, reverse.d) == \
        ("proved-not", "containment", (0, 3), 0, (0.01, 1.0))
    assert verdicts[(2, 3)].status == "unresolved" and verdicts[(0, 2)].status == "sampled-contained"
    chained = verdicts[(1, 4)]      # 0 ⊄ 4 and 0 ⊆ 1 (rule 1 on the carried proof, which is
    assert (chained.status, chained.certificate, chained.via, chained.d) == \
        ("proved-not", "containment", (0, 4), (0.01, 1.0))      # reached before 1 ⊄ 3 and 4 ⊆ 3)
    assert verdicts[(0, 3)].certificate == "farkas"
    proved = sorted(key for key, v in verdicts.items() if v.proved)
    assert proved == [(0, 1), (0, 3), (0, 4), (1, 3), (1, 4), (4, 3)]

    record = isotropy.Transfer(x=(1.0, 0.0), cos=-1e-12, mu=1e-6, rho=1e-11, lambda_prime=1e-6,
                               gamma=1.0, kappa=1.0, n_b=2, n_c=2, shells=3, fit=1e-12,
                               float_stack=False, kernel_dim=0, kernel_residual=0.0)
    verdicts = fresh()
    verdicts[(0, 3)] = isotropy.PairVerdict(0, 3, "proved-not", "transfer", 4, 0, d=(0.01, 0.1),
                                            witness=witness, transfer=record, via=(2, 3))
    isotropy._transfers(verdicts, list(range(n)), grams, dark, silent, n=n, seed=1, rtol=1e-4,
                        restarts=2)
    assert verdicts[(1, 3)].certificate == "containment" and verdicts[(1, 3)].transfer is record

    verdicts = fresh()
    verdicts[(1, 3)] = isotropy.PairVerdict(1, 3, "proved-contained", "span")
    with pytest.raises(RuntimeError, match="two certificates disagree"):
        isotropy._transfers(verdicts, list(range(n)), grams, dark, silent, n=n, seed=1,
                            rtol=1e-4, restarts=2)


def _kernel_stack(d: float, r: float) -> np.ndarray:
    """Three shells of a 3-amplitude ``b`` whose third amplitude is a near-kernel: shell s is a_s·I on (0, 1), a coupling r to the kernel direction and r²·2/a_s on it, a = (1 + d, 1, 2)."""
    shells = []
    for a in (1.0 + d, 1.0, 2.0):
        shells.append(np.array([[a, 0.0, r], [0.0, a, 0.0], [r, 0.0, 2.0 * r * r / a]]))
    return np.array(shells)


def _kernel_witness():
    """A witness whose interior ŷ = (1, −1, 0)/√2 puts M(ŷ) = (d/√2)·I on the live directions: the margin is d/√2 over Γ, as small as the stack's d."""
    return isotropy.Witness(
        draw=1, t=(1.0, 1.0, 1.0), live=(0, 1, 2), y=(1.0, -1.0, 0.0), weights=None,
        kernel_dim=1, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"), ratio=1e-9,
        rounding_bound=1e-15, exact=True, d=(0.01, 0.1),
        interior=(1.0 / np.sqrt(2.0), -1.0 / np.sqrt(2.0), 0.0), margin=1e-9)


def test_the_fit_transfer_reads_the_kernel_leak_of_the_stack_it_bounds():
    """A cone margin on b's projected stack is not a margin on b's full stack: r_K·Y·(2ρ + ρ²) is subtracted, and a margin it exceeds fires nothing.

    ``b`` has a near-kernel (coupling r = 2e-9, r_K ≈ 5e-10, accepted: r_K ≤
    :data:`isotropy.INTENSITY_RTOL`); ``c`` is a one-amplitude family
    whose image point is (1, 3, 1), at cos(ŷ, I_c) = −0.43, far below any
    positive margin.  Reviewer's item 1 on #853: with d = 2e-9 the
    projected margin is positive (1.4e-9 over Γ), so a bound read on the
    projected stack alone fires, while a model of ``b`` with a kernel
    component as large as its live one can leave the cone by 3·r_K·Y =
    2.1e-9; the transfer then declines.  Positive arms: the same family
    at d = 1 (the margin dwarfs the leak) fires, with the cone narrowed by
    the 1 + ρ² of the norm bound, and at r = 0 (an exact kernel) it
    fires at any d, the record carrying both kernel numbers.
    """
    dark = np.zeros(3, dtype=bool)
    grams_c = np.array([1.0, 3.0, 1.0]).reshape(3, 1, 1)
    witness = _kernel_witness()
    y_hat = np.array(witness.interior)

    thin = _kernel_stack(2e-9, 2e-9)
    projected, kernel, residual = isotropy._live_projection(thin)
    assert kernel == 1 and 4e-10 < residual <= isotropy.INTENSITY_RTOL
    assert isotropy._cone_margin(projected, y_hat)[2] > 0.0      # what the old code read, and fired on
    assert isotropy._fit_transfer(witness, thin, dark, grams_c, [1.0]) == (False, None)
    assert isotropy._transfer_margin(thin, y_hat)[2] < 0.0

    wide = _kernel_stack(1.0, 2e-9)
    fires, record = isotropy._fit_transfer(witness, wide, dark, grams_c, [1.0])
    assert fires and record.cos < -0.4 and record.kernel_dim == 1
    assert 4e-10 < record.kernel_residual <= isotropy.INTENSITY_RTOL
    lam, gamma, mu = isotropy._cone_margin(isotropy._live_projection(wide)[0], y_hat)
    assert 0.0 < record.mu < mu and record.mu == pytest.approx(record.lambda_prime / record.gamma)

    exact = _kernel_stack(2e-9, 0.0)
    fires, record = isotropy._fit_transfer(witness, exact, dark, grams_c, [1.0])
    assert fires and record.kernel_dim == 1 and record.kernel_residual < 1e-15 and record.mu > 0.0
    assert isotropy._verify_transfer(witness, exact, dark, grams_c, record)


def test_a_propagated_transfer_verdict_keeps_its_record_and_is_not_fitted_again():
    """:func:`isotropy._propagate` carries ``transfer`` to the isometric copies, so :func:`isotropy._transfers`' loop, which skips a verdict with a record, skips the copy too.

    Reviewer's item 2 on #853: the copy (2, 1) of a ``transfer`` verdict
    (0, 1) came out ``propagated`` with ``transfer=None``, and the loop
    read its witness (0's draw, not a point of 2's image) as 2's own and
    fitted every third family to it.  Here 0 ≅ 2, nothing else is an
    isometric copy, and the fit is stubbed to count its calls: none may be
    made, for the source or its copy.
    """
    _, parts = isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_OUT)
    witness = isotropy.Witness(
        draw=1, t=tuple(SYNTHETIC_OUT), live=(0, 1, 2), y=tuple(parts["y"]), weights=None,
        kernel_dim=0, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"),
        ratio=parts["ratio"], rounding_bound=parts["rounding_bound"], exact=True,
        d=(0.01, 0.1), interior=tuple(parts["interior"]), margin=parts["margin"])
    record = isotropy.Transfer(x=(1.0, 0.0), cos=-1e-12, mu=1e-6, rho=1e-11, lambda_prime=1e-6,
                               gamma=1.0, kappa=1.0, n_b=2, n_c=2, shells=3, fit=1e-12,
                               float_stack=False, kernel_dim=0, kernel_residual=0.0)
    n = 4
    verdicts = {(i, j): isotropy.PairVerdict(i, j, "unresolved", None, reason="joined")
                for i in range(n) for j in range(n) if i != j}
    verdicts[(0, 1)] = isotropy.PairVerdict(0, 1, "proved-not", "transfer", d=(0.01, 0.1),
                                            witness=witness, transfer=record, via=(3, 1))
    copies = [0, 1, 0, 3]
    isotropy._propagate(verdicts[(0, 1)], verdicts, copies, n)
    copy = verdicts[(2, 1)]
    assert (copy.status, copy.certificate, copy.via) == ("proved-not", "propagated", (0, 1))
    assert copy.transfer is record and copy.witness is witness

    calls = []
    original = isotropy._transfer_fit
    isotropy._transfer_fit = lambda *args, **kwargs: calls.append(args) or None
    try:
        isotropy._transfers(verdicts, copies, [SYNTHETIC_STACK] * n,
                            [np.zeros(3, dtype=bool)] * n, [False] * n, n=n, seed=1, rtol=1e-4,
                            restarts=2)
    finally:
        isotropy._transfer_fit = original
    assert calls == []


def test_the_fit_transfer_reads_the_margin_and_not_the_sign():
    """A point of ``c``'s image at cos = +μ/2, the wrong side of zero for the sign test, fires; one at cos = 2μ, inside the cone, does not; one lighting a dark shell of ``b`` is refused.

    ``b`` is the synthetic stack with its certificate for t = (1, 1, 2.5)
    and a fourth, dark shell; ``c`` is a one-amplitude family whose single
    pattern is t̂ + ε·ŷ on the live shells, so its image is that ray and
    the cosine is ε to first order (ŷ its interior, μ its margin).  Issue
    #565, item 6: "the sign test y·I_c < 0 is noise"; the decision is
    cos < μ − ρ, whatever the sign, a point inside the cone round ŷ is
    undecided, never a separation, and a point that lights a shell ``b``
    is dark at is another certificate's business (absence), so the
    transfer declines it.
    """
    stack = np.concatenate([SYNTHETIC_STACK, np.zeros((1, 2, 2))])      # shell 3 dark for b
    dark = np.array([False, False, False, True])
    _, parts = isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_OUT)
    witness = isotropy.Witness(
        draw=1, t=tuple(SYNTHETIC_OUT) + (0.0,), live=(0, 1, 2), y=tuple(parts["y"]),
        weights=None, kernel_dim=0, kernel_residual=0.0, kernel_amplitude_ratio=float("inf"),
        ratio=parts["ratio"], rounding_bound=parts["rounding_bound"], exact=True,
        d=(0.01, 0.1), interior=tuple(parts["interior"]), margin=parts["margin"])
    y_hat, mu = np.array(witness.interior), witness.margin
    t_hat = SYNTHETIC_OUT / np.linalg.norm(SYNTHETIC_OUT)
    for epsilon, should_fire in ((0.5 * mu, True), (2.0 * mu, False)):
        ray = t_hat + epsilon * y_hat                   # all positive: a valid 1 × 1 PSD stack
        assert np.all(ray > 0.0)
        grams_c = np.r_[ray, 0.0].reshape(4, 1, 1)
        fires, record = isotropy._fit_transfer(witness, stack, dark, grams_c, [1.0])
        assert record is not None and record.mu == pytest.approx(mu)
        exact = float(y_hat @ ray) / float(np.linalg.norm(ray))    # ε to first order
        assert record.cos == pytest.approx(exact, rel=1e-9) and record.cos > 0.0
        assert abs(record.cos - epsilon) <= 0.05 * epsilon
        assert fires is should_fire, (epsilon, record)
        assert record.rho < 1e-3 * mu
        lit = np.r_[ray, 0.5].reshape(4, 1, 1)         # the same ray, lighting b's dark shell
        assert isotropy._fit_transfer(witness, stack, dark, lit, [1.0]) == (False, None)


def test_the_witness_interior_is_the_duals_maximiser():
    """``Witness.interior`` is the unit direction at the dual's optimum, whose margin is decades above the quoted point's.

    On the synthetic stack: λ_min/|λ|_max of M(ŷ) equals the dual's
    optimum, the stored margin is λ′/Γ for it (:func:`isotropy._cone_margin`),
    and the quoted y, a step inside the PSD boundary by construction
    (ratio :data:`isotropy.FARKAS_QUOTE`), has a margin at least a hundred
    times smaller; a transfer read on the quoted point would leave the
    rounding allowance a real share of the bound.
    """
    dual, parts = isotropy._farkas_certificate(SYNTHETIC_STACK, SYNTHETIC_OUT)
    interior = np.array(parts["interior"])
    assert np.linalg.norm(interior) == pytest.approx(1.0)
    stack = SYNTHETIC_STACK / np.max(np.abs(SYNTHETIC_STACK))
    assert isotropy._spectrum_ratio(stack, interior) == pytest.approx(dual, rel=1e-9)
    lam, gamma, mu = isotropy._cone_margin(stack, interior)
    assert parts["margin"] == pytest.approx(mu) and 0.0 < mu < 1.0
    quoted = np.array(parts["y"]) / np.linalg.norm(parts["y"])
    assert mu >= 100.0 * isotropy._cone_margin(stack, quoted)[2]
