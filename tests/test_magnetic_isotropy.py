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
    """Control (ii): +1 on a moment gives grey stabilisers, which forbid every moment."""
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
                sink.append(isotropy._candidate_group(little, cell, direction.stabilizer))
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
PNMA_SB_DISPLACIVE_BNS = {"4.8", "11.51", "6.19", "2.5"}


def test_pnma_sb_displacive_candidates_verify_true():
    """Regression: the four Type-II displacive candidates, checked by their own rule.

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
    """
    found = isotropy.candidates("P n m a", Q22_SITE, Q22_K, kind="displacive", verify=False)
    candidate = next(c for c in found if c.label == "S1(rank 2)#3")
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

    pattern = candidate.configurations[2][atom]   # d = (0, 0.624, -0.624), Q21's own numbers
    assert pattern == pytest.approx((0, 0.624, -0.624), abs=2e-4)

    old_rule = allowed_displacement_basis([op])         # no phases: the pre-Q22 rule
    new_rule = allowed_displacement_basis([op], phases=[-1])   # Q22's fix

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
    """The convention pin: contravariant fractional components times Aᵀ.

    :func:`isotropy.moment_cartesian` goes through M-5's ``moment_to_cartesian``,
    which speaks magCIF's unit-vector ``crystalaxis`` basis; that it comes back
    equal to Aᵀ·m is the statement that the two conventions were reconciled and
    not merely both used.
    """
    lattice = isotropy.compatible_cell("P 6_3 c m")
    moments = np.array([[0.3, -0.7, 1.1], [1.0, 1.0, 0.0]])
    assert np.allclose(isotropy.moment_cartesian(moments, lattice), moments @ lattice)


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


def test_the_jacobian_deficit_is_the_undeterminable_direction():
    """A cubic ferromagnet has two free amplitudes a powder cannot see, and says so."""
    found = isotropy.candidates("F m -3 m", (0, 0, 0), GAMMA)
    reflections = isotropy.reflections(found.lattice, 2.0)
    general = max(found.candidates, key=lambda c: c.free_amplitudes)
    assert general.free_amplitudes == 3
    assert isotropy.determinable_amplitudes(general, reflections) == 1


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
